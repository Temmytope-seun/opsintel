"""Risk scoring.

1. SLA risk for next week (per service) - explainable logistic regression on a
   service x week panel, temporal train/test split, bootstrap uncertainty, and a
   persistence baseline to beat.
2. Delivery-delay risk for open service requests - transparent rules-based score.
"""
from __future__ import annotations

from datetime import timedelta
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

from opsintel import config, db

FEATURES = {
    "incidents_7d": "Incidents opened in the last 7 days",
    "breaches_7d": "SLA breaches among last-7-day incidents",
    "breach_rate_28d": "SLA breach rate over the last 28 days",
    "alerts_7d": "Monitoring alerts in the last 7 days",
    "critical_alerts_7d": "Critical/major alerts in the last 7 days",
    "alert_trend": "Alerts last 7 days vs weekly average of the prior 21 days",
    "res_ratio_28d": "Mean resolution time as a multiple of SLA target (28 days)",
    "high_priority_7d": "P1/P2 incidents in the last 7 days",
}
SLA_COMPLIANCE_TARGET = 0.90   # a service "misses SLA" in a week if <90% of incidents meet target
TRAIN_END = pd.Timestamp("2026-04-01")


def _panel(con=None) -> pd.DataFrame:
    inc = db.query_df("SELECT service_id, opened_at, priority, sla_breached, resolution_hours, sla_target_hours FROM incidents", (), con)
    al = db.query_df("SELECT service_id, ts, severity FROM alerts", (), con)
    inc["opened_at"] = pd.to_datetime(inc.opened_at)
    al["ts"] = pd.to_datetime(al.ts)
    snap = pd.Timestamp(config.SNAPSHOT_DATE) + timedelta(days=1)  # exclusive end
    services = sorted(inc.service_id.unique())
    ends = [snap - timedelta(days=7 * k) for k in range(0, 200)]
    ends = [e for e in ends if e - timedelta(days=28) >= pd.Timestamp(config.DATA_START)]
    rows = []
    for sid in services:
        si, sa = inc[inc.service_id == sid], al[al.service_id == sid]
        for end in ends:
            w7 = si[(si.opened_at >= end - timedelta(days=7)) & (si.opened_at < end)]
            w28 = si[(si.opened_at >= end - timedelta(days=28)) & (si.opened_at < end)]
            a7 = sa[(sa.ts >= end - timedelta(days=7)) & (sa.ts < end)]
            a21 = sa[(sa.ts >= end - timedelta(days=28)) & (sa.ts < end - timedelta(days=7))]
            nxt = si[(si.opened_at >= end) & (si.opened_at < end + timedelta(days=7))]
            known = nxt.sla_breached.dropna()
            label = np.nan
            if end < snap and len(known) > 0:
                label = float(known.mean() > 1 - SLA_COMPLIANCE_TARGET)
            k28 = w28.sla_breached.dropna()
            rows.append({
                "service_id": sid, "window_end": end,
                "incidents_7d": len(w7), "breaches_7d": float(w7.sla_breached.fillna(0).sum()),
                "breach_rate_28d": float(k28.mean()) if len(k28) else 0.0,
                "alerts_7d": len(a7), "critical_alerts_7d": int(a7.severity.isin(["critical", "major"]).sum()),
                "alert_trend": (len(a7) + 1) / (len(a21) / 3 + 1),
                "res_ratio_28d": float((w28.resolution_hours / w28.sla_target_hours).mean()) if w28.resolution_hours.notna().any() else 0.0,
                "high_priority_7d": int(w7.priority.isin(["P1", "P2"]).sum()),
                "label_next_week_miss": label,
            })
    return pd.DataFrame(rows)


def _fit(X, y, seed=0):
    sc = StandardScaler().fit(X)
    m = LogisticRegression(C=0.5, class_weight="balanced", max_iter=1000, random_state=seed).fit(sc.transform(X), y)
    return sc, m


@lru_cache(maxsize=2)
def _model_bundle(db_path: str):
    panel = _panel()
    lab = panel.dropna(subset=["label_next_week_miss"])
    feats = list(FEATURES)
    train, test = lab[lab.window_end < TRAIN_END], lab[lab.window_end >= TRAIN_END]
    sc, m = _fit(train[feats], train.label_next_week_miss)
    p_test = m.predict_proba(sc.transform(test[feats]))[:, 1]
    # Persistence baseline: "missed this week -> will miss next week".
    this_week = panel.set_index(["service_id", "window_end"]).label_next_week_miss
    prev_label = [this_week.get((r.service_id, r.window_end - timedelta(days=7)), np.nan) for r in test.itertuples()]
    base = pd.Series(prev_label).fillna(lab.label_next_week_miss.mean()).to_numpy()
    k = 14
    top_model = test.assign(p=p_test).sort_values("p", ascending=False).head(k).label_next_week_miss.mean()
    evaluation = {
        "train_windows": int(len(train)), "test_windows": int(len(test)),
        "train_period": f"to {TRAIN_END.date()}", "test_period": f"{TRAIN_END.date()} to {config.SNAPSHOT_DATE}",
        "positive_rate_test": round(float(test.label_next_week_miss.mean()), 3),
        "model_auc": round(float(roc_auc_score(test.label_next_week_miss, p_test)), 3),
        "model_brier": round(float(brier_score_loss(test.label_next_week_miss, p_test)), 3),
        "baseline_persistence_auc": round(float(roc_auc_score(test.label_next_week_miss, base)), 3),
        "baseline_persistence_brier": round(float(brier_score_loss(test.label_next_week_miss, base)), 3),
        f"model_precision_at_{k}": round(float(top_model), 3),
    }
    # Final model on all labelled windows + bootstrap ensemble for uncertainty.
    sc_all, m_all = _fit(lab[feats], lab.label_next_week_miss)
    rng = np.random.default_rng(7)
    boots = []
    for b in range(40):
        idx = rng.integers(0, len(lab), len(lab))
        boots.append(_fit(lab[feats].iloc[idx], lab.label_next_week_miss.iloc[idx], seed=b))
    return panel, sc_all, m_all, boots, evaluation


def sla_risk_next_week(top_n: int = 14, con=None) -> dict:
    panel, sc, m, boots, evaluation = _model_bundle(str(config.DB_PATH))
    feats = list(FEATURES)
    cur = panel[panel.window_end == panel.window_end.max()].copy()
    Xs = sc.transform(cur[feats])
    cur["risk"] = m.predict_proba(Xs)[:, 1]
    ens = np.array([mm.predict_proba(s.transform(cur[feats]))[:, 1] for s, mm in boots])
    cur["risk_low"], cur["risk_high"] = np.percentile(ens, 10, axis=0), np.percentile(ens, 90, axis=0)
    contrib = Xs * m.coef_[0]
    names = db.query_df("SELECT service_id, name, owner_group, tier FROM services", (), con).set_index("service_id")
    out = []
    for i, r in enumerate(cur.itertuples()):
        order = np.argsort(-contrib[i])
        drivers = [{"factor": FEATURES[feats[j]], "value": round(float(getattr(r, feats[j])), 3),
                    "contribution": round(float(contrib[i][j]), 3)} for j in order[:3] if contrib[i][j] > 0]
        band = "High" if r.risk >= 0.6 else "Medium" if r.risk >= 0.35 else "Low"
        out.append({"service_id": r.service_id, "service": names.loc[r.service_id, "name"],
                    "owner_group": names.loc[r.service_id, "owner_group"], "tier": names.loc[r.service_id, "tier"],
                    "risk_pct": round(100 * r.risk, 1), "interval_pct": [round(100 * r.risk_low, 1), round(100 * r.risk_high, 1)],
                    "band": band, "top_drivers": drivers})
    out.sort(key=lambda d: -d["risk_pct"])
    week_start = (cur.window_end.max()).date()
    top = out[0]
    return {
        "metric": "sla_risk_next_week", "forecast_week": f"{week_start} to {week_start + timedelta(days=6)}",
        "definition": f"Probability the service misses {int(SLA_COMPLIANCE_TARGET * 100)}% SLA compliance next week. "
                      "Interval = 10th-90th percentile of a 40-model bootstrap ensemble.",
        "model": "Logistic regression (standardised features, class-balanced); drivers = coefficient x standardised value",
        "evaluation": evaluation, "data": out[:top_n],
        "summary": f"Highest SLA risk for {week_start}: {top['service']} at {top['risk_pct']}% "
                   f"(interval {top['interval_pct'][0]}-{top['interval_pct'][1]}%).",
        "chart": {"type": "bar", "x": "service", "y": ["risk_pct"], "title": "SLA miss risk next week (%)"},
    }


def delivery_delay_risk(limit: int = 15, con=None) -> dict:
    """Score open service requests for risk of missing their committed date.

    score = 40 x elapsed share of target window (capped at 1)
          + 30 if blocked on a dependency
          + 30 x historical late rate for that request type (last 6 months)
    Requests already past due score 100.
    """
    snap = pd.Timestamp(config.SNAPSHOT_DATE) + timedelta(days=1)
    open_r = db.query_df("""SELECT r.request_id, r.opened_at, r.due_at, r.request_type, r.target_days, r.blocked_reason,
                                   r.assignment_group, s.name AS service, r.customer_id
                            FROM service_requests r JOIN services s USING (service_id) WHERE r.closed_at IS NULL""", (), con)
    hist = db.query_df("""SELECT request_type, 1.0 - AVG(met_due_date) AS late_rate, COUNT(*) AS n
                          FROM service_requests WHERE closed_at >= date(:snap, '-6 months') GROUP BY request_type""",
                       {"snap": str(snap.date())}, con).set_index("request_type")
    open_r["opened_at"], open_r["due_at"] = pd.to_datetime(open_r.opened_at), pd.to_datetime(open_r.due_at)
    elapsed = (snap - open_r.opened_at).dt.total_seconds() / 86400
    open_r["elapsed_share"] = (elapsed / open_r.target_days).clip(0, None).round(2)
    open_r["hist_late_rate"] = open_r.request_type.map(hist.late_rate).fillna(0.2).round(2)
    open_r["overdue"] = open_r.due_at < snap
    score = 40 * open_r.elapsed_share.clip(upper=1) + 30 * open_r.blocked_reason.notna() + 30 * open_r.hist_late_rate
    open_r["risk_score"] = np.where(open_r.overdue, 100, score).round(1)
    open_r["days_to_due"] = ((open_r.due_at - snap).dt.total_seconds() / 86400).round(1)
    open_r = open_r.sort_values(["risk_score", "days_to_due"], ascending=[False, True]).head(limit)
    open_r["opened_at"] = open_r.opened_at.dt.strftime("%Y-%m-%d")
    open_r["due_at"] = open_r.due_at.dt.strftime("%Y-%m-%d")
    cols = ["request_id", "service", "request_type", "opened_at", "due_at", "days_to_due", "blocked_reason",
            "elapsed_share", "hist_late_rate", "overdue", "risk_score", "assignment_group"]
    recs = open_r[cols].astype(object).where(open_r[cols].notna(), None).to_dict("records")
    n_open = int(db.query_df("SELECT COUNT(*) n FROM service_requests WHERE closed_at IS NULL", (), con).n.iloc[0])
    blocked = sum(1 for r in recs if r["blocked_reason"])
    return {"metric": "delivery_delay_risk", "as_of": config.SNAPSHOT_DATE.isoformat(), "open_requests": n_open,
            "method": delivery_delay_risk.__doc__.split("\n\n")[1].strip(), "data": recs,
            "summary": f"{n_open} open requests; top {len(recs)} at-risk listed, {blocked} of them blocked on a dependency. "
                       f"Highest: {recs[0]['request_id']} ({recs[0]['request_type']}), score {recs[0]['risk_score']}." if recs else "No open requests.",
            "chart": {"type": "bar", "x": "request_id", "y": ["risk_score"], "title": "Delivery delay risk score"}}
