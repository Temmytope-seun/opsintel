"""Anomaly detection: Isolation Forest on service-day operating signals, robust
z-scores on monthly cost lines."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from opsintel import config, db

SIGNALS = ["incidents", "breaches", "alerts", "critical_alerts", "outage_minutes"]


def operational_anomalies(days: int = 30, limit: int = 12, contamination: float = 0.02, con=None) -> dict:
    inc = db.query_df("""SELECT service_id, date(opened_at) AS day, COUNT(*) AS incidents,
                                SUM(COALESCE(sla_breached,0)) AS breaches, SUM(outage_minutes) AS outage_minutes
                         FROM incidents GROUP BY service_id, day""", (), con)
    al = db.query_df("""SELECT service_id, date(ts) AS day, COUNT(*) AS alerts,
                               SUM(severity IN ('critical','major')) AS critical_alerts
                        FROM alerts GROUP BY service_id, day""", (), con)
    days_idx = pd.date_range(config.DATA_START, config.SNAPSHOT_DATE).strftime("%Y-%m-%d")
    svcs = db.query_df("SELECT service_id, name FROM services", (), con)
    grid = pd.MultiIndex.from_product([svcs.service_id, days_idx], names=["service_id", "day"]).to_frame(index=False)
    df = grid.merge(inc, how="left").merge(al, how="left").fillna(0)
    out = []
    for sid, g in df.groupby("service_id"):
        # Standardise per service so a busy service is not "anomalous" just for being busy.
        X = (g[SIGNALS] - g[SIGNALS].mean()) / g[SIGNALS].std().replace(0, 1)
        f = IsolationForest(n_estimators=200, contamination=contamination, random_state=0).fit(X)
        g = g.assign(score=-f.score_samples(X), flag=f.predict(X) == -1, **{f"z_{c}": X[c] for c in SIGNALS})
        out.append(g)
    res = pd.concat(out)
    start = (pd.Timestamp(config.SNAPSHOT_DATE) - pd.Timedelta(days=days - 1)).strftime("%Y-%m-%d")
    recent = res[res.flag & (res.day >= start)].merge(svcs, on="service_id").sort_values("score", ascending=False)
    recs = []
    for r in recent.head(limit).itertuples():
        zs = {c: getattr(r, f"z_{c}") for c in SIGNALS}
        driver = max(zs, key=lambda c: zs[c])
        recs.append({"day": r.day, "service": r.name, "anomaly_score": round(r.score, 3),
                     "main_signal": driver, "signal_value": int(getattr(r, driver)), "z_score": round(zs[driver], 1),
                     **{c: int(getattr(r, c)) for c in SIGNALS}})
    by_svc = recent.groupby("name").size().sort_values(ascending=False)
    return {"metric": "operational_anomalies", "window": f"{start} to {config.SNAPSHOT_DATE}",
            "method": f"Isolation Forest per service on daily {', '.join(SIGNALS)} (contamination={contamination})",
            "anomalous_days_by_service": {k: int(v) for k, v in by_svc.items()}, "data": recs,
            "summary": (f"{len(recent)} anomalous service-days in the last {days} days; most affected: "
                        + ", ".join(f"{k} ({v})" for k, v in by_svc.head(3).items()) + ".") if len(recent) else "No anomalies flagged.",
            "chart": {"type": "scatter", "x": "day", "y": ["anomaly_score"], "color": "service", "title": "Recent operational anomalies"}}


def cost_anomalies(threshold: float = 3.5, con=None) -> dict:
    df = db.query_df("""SELECT c.month, s.name AS service, c.cost_type, c.amount_gbp, c.description
                        FROM costs c JOIN services s USING (service_id) ORDER BY c.month""", (), con)
    df["mom_change"] = df.groupby(["service", "cost_type"]).amount_gbp.diff()
    latest = df.month.max()
    recs = []
    for (svc, ctype), g in df.groupby(["service", "cost_type"]):
        hist = g[g.month < latest].mom_change.dropna()
        cur = g[g.month == latest]
        if cur.empty or len(hist) < 6:
            continue
        med, mad = hist.median(), (hist - hist.median()).abs().median() or 1.0
        z = 0.6745 * (cur.mom_change.iloc[0] - med) / mad
        if abs(z) >= threshold:
            recs.append({"month": latest, "service": svc, "cost_type": ctype, "amount_gbp": round(float(cur.amount_gbp.iloc[0]), 2),
                         "change_vs_prev_gbp": round(float(cur.mom_change.iloc[0]), 2), "robust_z": round(float(z), 1),
                         "ledger_narrative": cur.description.iloc[0]})
    recs.sort(key=lambda r: -abs(r["robust_z"]))
    return {"metric": "cost_anomalies", "month": latest, "method": f"Robust z-score (median/MAD) of month-on-month change, |z| >= {threshold}",
            "data": recs, "summary": f"{len(recs)} cost lines in {latest} moved abnormally vs their own history."
            + (f" Largest: {recs[0]['service']} {recs[0]['cost_type']} ({recs[0]['change_vs_prev_gbp']:+,.0f})." if recs else "")}
