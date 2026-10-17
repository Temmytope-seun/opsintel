"""Monthly forecasts of incident volume and operating cost, three months ahead.

Small-data, transparent methods only (18 months of history is too short for anything heavier):

* naive      - next months equal the last complete month (the baseline to beat)
* mean3      - average of the last three months
* holt       - damped Holt linear trend, smoothing parameters picked by in-sample one-step error
* seasonal   - same month last year (only offered with 24+ months of history)

Each series is backtested with a rolling origin over its last BACKTEST_ORIGINS months. The method
with the lowest backtest MAE is used. The 80% range is the estimate plus or minus the 80th percentile of
that method's absolute backtest errors.
Like the risk score, this is a planning aid with stated uncertainty, not a commitment.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from opsintel import config, db
from opsintel.analytics.risk import InsufficientData

HORIZON = 3
BACKTEST_ORIGINS = 6
MIN_MONTHS = BACKTEST_ORIGINS + 3  # enough to fit the earliest backtest origin
MAX_GROUPS = 8

INCIDENT_GROUPS = {"category": "category", "service": "service_name", "business_unit": "business_unit", "priority": "priority"}
COST_GROUPS = {"business_unit": "b.name", "cost_type": "c.cost_type", "service": "s.name"}


# ------------------------------------------------------------------ methods

def _naive(y: np.ndarray, h: int) -> np.ndarray:
    return np.repeat(y[-1], h).astype(float)


def _mean3(y: np.ndarray, h: int) -> np.ndarray:
    return np.repeat(y[-3:].mean(), h)


def _holt_run(y, alpha, beta, phi):
    level, trend, sse = y[0], y[1] - y[0], 0.0
    for t in range(1, len(y)):
        sse += (y[t] - (level + phi * trend)) ** 2
        new_level = alpha * y[t] + (1 - alpha) * (level + phi * trend)
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        level = new_level
    return level, trend, sse


def _holt(y: np.ndarray, h: int, phi: float = 0.9) -> np.ndarray:
    y = y.astype(float)
    best = min(((a, b) for a in (0.2, 0.4, 0.6, 0.8) for b in (0.05, 0.1, 0.2)),
               key=lambda ab: _holt_run(y, ab[0], ab[1], phi)[2])
    level, trend, _ = _holt_run(y, *best, phi)
    return np.array([level + trend * sum(phi ** i for i in range(1, k + 1)) for k in range(1, h + 1)])


def _seasonal(y: np.ndarray, h: int) -> np.ndarray:
    return np.array([y[len(y) - 12 + k] for k in range(h)], dtype=float)


METHODS = {"naive": _naive, "mean3": _mean3, "holt": _holt, "seasonal": _seasonal}
METHOD_LABEL = {"naive": "last month repeated", "mean3": "3-month average", "holt": "damped Holt trend",
                "seasonal": "same month last year"}


def _backtest(y: np.ndarray, method: str) -> np.ndarray:
    """Signed errors (actual - forecast) from rolling origins over the last BACKTEST_ORIGINS months."""
    errs = []
    n = len(y)
    for origin in range(n - BACKTEST_ORIGINS, n):
        f = METHODS[method](y[:origin], HORIZON)
        for k in range(HORIZON):
            if origin + k < n:
                errs.append(y[origin + k] - f[k])
    return np.array(errs)


def forecast_series(y: np.ndarray) -> dict:
    """Pick the best method by backtest MAE and forecast HORIZON months with an 80% interval."""
    y = np.asarray(y, dtype=float)
    candidates = [m for m in METHODS if m != "seasonal" or len(y) >= 24 + BACKTEST_ORIGINS]
    errors = {m: _backtest(y, m) for m in candidates}
    mae = {m: float(np.abs(e).mean()) for m, e in errors.items()}
    method = min(candidates, key=lambda m: (mae[m], m != "naive"))  # ties go to the simpler baseline
    point = np.clip(METHODS[method](y, HORIZON), 0, None)
    width = float(np.quantile(np.abs(errors[method]), 0.8))  # symmetric, so the range always contains the estimate
    return {"method": method, "point": point, "low": np.clip(point - width, 0, None), "high": point + width,
            "mae": mae[method], "naive_mae": mae["naive"], "all_mae": mae}


# ------------------------------------------------------------------ data

def last_complete_month() -> str:
    snap = config.SNAPSHOT_DATE
    month = pd.Period(snap, freq="M")
    return str(month if (snap + timedelta(days=1)).day == 1 else month - 1)


def _months() -> list[str]:
    start = pd.Period(config.DATA_START, freq="M")
    if config.DATA_START.day != 1:
        start += 1  # a partial first month would understate volume
    return [str(p) for p in pd.period_range(start, pd.Period(last_complete_month(), freq="M"), freq="M")]


def _trim(panel: pd.DataFrame) -> pd.DataFrame:
    """Keep the latest continuous run of history: start after the last gap of 3+ empty months (e.g. scattered
    years-old demo records in a ServiceNow instance) and drop a partial-looking first month (< half the median)."""
    total = panel.sum(axis=1).to_numpy()
    start, zeros = 0, 0
    for i, v in enumerate(total):
        zeros = zeros + 1 if v == 0 else 0
        if zeros >= 3:
            start = i + 1
    while start < len(total) - 1 and total[start] == 0:
        start += 1
    if start < len(total) - 1 and total[start] < 0.5 * np.median(total[start:]):
        start += 1
    return panel.iloc[start:]


def _panel(metric: str, group_by: str | None, con=None) -> tuple[pd.DataFrame, str]:
    if metric == "incidents":
        col = INCIDENT_GROUPS[group_by] if group_by else "'Total'"
        sql = (f"SELECT opened_month AS month, {col} AS grp, COUNT(*) AS value FROM v_incidents "
               f"GROUP BY opened_month, grp ORDER BY month")
    else:
        col = COST_GROUPS[group_by] if group_by else "'Total'"
        sql = (f"SELECT c.month AS month, {col} AS grp, ROUND(SUM(c.amount_gbp), 2) AS value FROM costs c "
               f"JOIN services s USING (service_id) JOIN business_units b USING (bu_id) GROUP BY c.month, grp ORDER BY month")
    df = db.query_df(sql, (), con)
    months = _months()
    if df.empty:
        raise InsufficientData(f"This data source has no {'incident' if metric == 'incidents' else 'cost'} history to forecast.")
    panel = _trim(df.pivot_table(index="month", columns="grp", values="value", aggfunc="sum").reindex(months).fillna(0))
    if len(panel) < MIN_MONTHS:
        raise InsufficientData(f"A forecast needs at least {MIN_MONTHS} complete months of continuous history; this source "
                               f"has {len(panel)}.")
    if panel.shape[1] > MAX_GROUPS:
        keep = panel.tail(3).sum().sort_values(ascending=False).index[:MAX_GROUPS - 1]
        panel = panel[list(keep)].assign(Other=panel.drop(columns=keep).sum(axis=1))
    return panel, sql


def _forecast(metric: str, group_by: str | None, con=None) -> dict:
    panel, sql = _panel(metric, group_by, con)
    last = panel.index[-1]
    future = [str(pd.Period(last, freq="M") + k) for k in range(1, HORIZON + 1)]
    nd = 0
    series = {"Total": panel.sum(axis=1)} if group_by else {}
    series.update({str(g): panel[g] for g in panel.columns})
    rows, groups = [], []
    for name, s in series.items():
        r = forecast_series(s.to_numpy())
        for k, m in enumerate(future):
            rows.append({"group": name, "month": m, "forecast": round(float(r["point"][k]), nd),
                         "low_80": round(float(r["low"][k]), nd), "high_80": round(float(r["high"][k]), nd)})
        groups.append({"group": name, "last_month": last, "last_month_actual": round(float(s.iloc[-1]), nd),
                       "last_3m_average": round(float(s.tail(3).mean()), nd),
                       "next_3m_total_forecast": round(float(r["point"].sum()), nd),
                       "change_vs_last_3m_pct": round(100 * (r["point"].sum() / s.tail(3).sum() - 1), 1) if s.tail(3).sum() else None,
                       "method": METHOD_LABEL[r["method"]], "backtest_mae": round(r["mae"], 1),
                       "naive_backtest_mae": round(r["naive_mae"], 1),
                       "skill_vs_naive_pct": round(100 * (1 - r["mae"] / r["naive_mae"]), 1) if r["naive_mae"] else None})
    total = groups[0]
    unit = "incidents" if metric == "incidents" else "GBP"
    fmt = (lambda v: f"{v:,.0f}") if metric == "incidents" else (lambda v: f"£{v:,.0f}")
    first = [r for r in rows if r["group"] == total["group"]][0]
    summary = (f"{'Incident volume' if metric == 'incidents' else 'Operating cost'} ({total['group']}) is forecast at "
               f"{fmt(first['forecast'])} for {first['month']} (80% range {fmt(first['low_80'])}-{fmt(first['high_80'])}) and "
               f"{fmt(total['next_3m_total_forecast'])} over {future[0]} to {future[-1]}, "
               f"{total['change_vs_last_3m_pct']:+.1f}% vs the last three months. Method: {total['method']} "
               f"(backtest MAE {total['backtest_mae']:,} vs {total['naive_backtest_mae']:,} for the naive baseline).")
    return {"summary": summary, "metric": metric, "unit": unit, "group_by": group_by or "total",
            "history_months": len(panel), "last_complete_month": last, "forecast_months": future,
            "data": rows, "groups": groups,
            "history": [{"month": m, **{str(k): round(float(v), nd) for k, v in panel.loc[m].items()}} for m in panel.index],
            "method_note": (f"Rolling-origin backtest over the last {BACKTEST_ORIGINS} months, {HORIZON} months ahead. Best of "
                            f"naive, 3-month average, damped Holt{', seasonal naive' if len(panel) >= 30 else ''} by mean absolute "
                            f"error; 80% range = estimate ± 80th percentile of its absolute backtest errors. Planning aid, not a commitment."),
            "sql": sql, "chart": {"type": "line", "x": "month", "y": "forecast", "series": "group"}}


def incident_forecast(group_by: str | None = None, con=None) -> dict:
    """Incidents opened per month, next three months, optionally by category/service/business_unit/priority."""
    if group_by and group_by not in INCIDENT_GROUPS:
        raise ValueError(f"group_by must be one of {sorted(INCIDENT_GROUPS)}")
    return _forecast("incidents", group_by, con)


def cost_forecast(group_by: str | None = None, con=None) -> dict:
    """Operating cost per month (GBP), next three months, optionally by business_unit/cost_type/service."""
    if group_by and group_by not in COST_GROUPS:
        raise ValueError(f"group_by must be one of {sorted(COST_GROUPS)}")
    return _forecast("cost", group_by, con)
