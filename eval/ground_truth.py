"""Independent ground truth computed with pandas from the generator's clean tables
(data/truth). Deliberately does NOT reuse the platform's SQL, so a bug in the KPI
layer shows up as an evaluation failure instead of being marked correct by itself."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from opsintel import config


@lru_cache(maxsize=None)
def t(name: str) -> pd.DataFrame:
    return pd.read_pickle(config.TRUTH_DIR / f"{name}.pkl")


def incidents() -> pd.DataFrame:
    inc = t("incidents").merge(t("sla_policies")[["priority", "resolution_target_hrs"]], on="priority")
    snap_end = pd.Timestamp(config.SNAPSHOT_DATE) + pd.Timedelta(days=1)
    hours = (inc.resolved_at - inc.opened_at).dt.total_seconds() / 3600
    elapsed = (snap_end - inc.opened_at).dt.total_seconds() / 3600
    inc["breach"] = pd.Series(pd.NA, index=inc.index, dtype="boolean")
    resolved = inc.resolved_at.notna()
    inc.loc[resolved, "breach"] = hours[resolved] > inc.resolution_target_hrs[resolved]
    late_open = ~resolved & (elapsed > inc.resolution_target_hrs)
    inc.loc[late_open, "breach"] = True
    inc["quarter"] = inc.opened_at.dt.to_period("Q").astype(str)
    inc["month"] = inc.opened_at.dt.strftime("%Y-%m")
    return inc


def breach_rate(quarter: str, category: str | None = None) -> float:
    inc = incidents()
    s = inc[(inc.quarter == quarter) & ((inc.category == category) if category else True)].breach.dropna()
    return round(100 * s.astype(float).mean(), 1)


def top_breach_category(quarter: str) -> str:
    inc = incidents()
    g = inc[inc.quarter == quarter].dropna(subset=["breach"]).groupby("category").breach.mean()
    return g.idxmax()


def incidents_in_month(month: str) -> int:
    return int((incidents().month == month).sum())


def root_cause_count(quarter: str, category: str) -> tuple[str, int]:
    inc = incidents()
    g = inc[(inc.quarter == quarter) & (inc.category == category)].root_cause.value_counts()
    return g.index[0], int(g.iloc[0])


def top_downtime_cause(months: int = 6) -> tuple[str, int]:
    inc = incidents()
    start = str(pd.Period(config.SNAPSHOT_DATE, freq="M") - (months - 1))
    g = inc[(inc.caused_outage) & (inc.month >= start)].groupby("root_cause").outage_minutes.sum().sort_values(ascending=False)
    return g.index[0], int(g.iloc[0])


def cost_total(month: str) -> float:
    c = t("costs")
    return round(float(c[c.month == month].amount_gbp.sum()), 2)


def top_cost_driver(month: str) -> tuple[str, str, float]:
    c = t("costs")
    prev = str(pd.Period(month, freq="M") - 1)
    p = c[c.month.isin([month, prev])].pivot_table(index=["service_id", "cost_type"], columns="month", values="amount_gbp")
    d = (p[month] - p[prev]).sort_values(ascending=False)
    sid, ctype = d.index[0]
    name = t("services").set_index("service_id").name[sid]
    return name, ctype, round(float(d.iloc[0]), 2)


def open_requests() -> int:
    return int(t("service_requests").closed_at.isna().sum())


def worst_on_time_request_type(quarter: str) -> str:
    r = t("service_requests")
    r = r[r.closed_at.notna()].copy()
    r["q"] = r.closed_at.dt.to_period("Q").astype(str)
    r = r[r.q == quarter]
    r["on_time"] = r.closed_at <= r.due_at
    g = r.groupby("request_type").on_time.mean().sort_values()
    return g.index[0]
