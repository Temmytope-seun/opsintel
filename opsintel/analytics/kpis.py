"""Deterministic KPI layer. Every number the assistant states should come from here
(or from the guarded SQL tool), never from the language model.

Each function returns a dict with:
    data     - list of records (the evidence)
    summary  - short machine-generated statement of the headline result
    sql      - the query that produced it (lineage for the evidence panel)
    chart    - optional rendering hint for the UI
"""
from __future__ import annotations

import re
from datetime import date

import pandas as pd

from opsintel import config, db

GROUPS = {
    "category": "category", "service": "service_name", "priority": "priority",
    "business_unit": "business_unit", "assignment_group": "assignment_group", "root_cause": "root_cause",
}


# ------------------------------------------------------------------ periods

def _quarter(d: date) -> str:
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def _shift_quarter(q: str, n: int) -> str:
    p = pd.Period(q, freq="Q") + n
    return f"{p.year}Q{p.quarter}"


def _shift_month(m: str, n: int) -> str:
    return str(pd.Period(m, freq="M") + n)


def resolve_period(period: str | None) -> tuple[str, str]:
    """Return ("quarter"|"month", value). Relative periods anchor on the data snapshot."""
    snap = config.SNAPSHOT_DATE
    p = (period or "last_quarter").strip().lower().replace(" ", "_")
    if p in ("this_month", "current_month", "latest_month", "last_month_in_data"):
        return "month", snap.strftime("%Y-%m")
    if p in ("previous_month", "prior_month"):
        return "month", _shift_month(snap.strftime("%Y-%m"), -1)
    if p in ("last_quarter", "latest_quarter", "this_quarter", "current_quarter"):
        return "quarter", _quarter(snap)
    if p in ("previous_quarter", "prior_quarter"):
        return "quarter", _shift_quarter(_quarter(snap), -1)
    m = re.fullmatch(r"(\d{4})[-_]?q([1-4])", p)
    if m:
        return "quarter", f"{m.group(1)}Q{m.group(2)}"
    m = re.fullmatch(r"q([1-4])[-_]?(\d{4})", p)
    if m:
        return "quarter", f"{m.group(2)}Q{m.group(1)}"
    if re.fullmatch(r"\d{4}-\d{2}", p):
        return "month", p
    raise ValueError(f"Unrecognised period {period!r}. Use YYYY-MM, YYYYQn, this_month, last_quarter, previous_quarter.")


def previous(kind: str, value: str) -> str:
    return _shift_quarter(value, -1) if kind == "quarter" else _shift_month(value, -1)


def _period_col(kind: str) -> str:
    return "opened_quarter" if kind == "quarter" else "opened_month"


def data_coverage() -> dict:
    return {"first_date": config.DATA_START.isoformat(), "snapshot_date": config.SNAPSHOT_DATE.isoformat(),
            "first_quarter": _quarter(config.DATA_START), "last_quarter": _quarter(config.SNAPSHOT_DATE)}


def _check_coverage(kind: str, value: str):
    start = pd.Period(config.DATA_START, freq="Q" if kind == "quarter" else "M")
    end = pd.Period(config.SNAPSHOT_DATE, freq="Q" if kind == "quarter" else "M")
    if not (start <= pd.Period(value, freq="Q" if kind == "quarter" else "M") <= end):
        raise ValueError(f"No data for {value}. Data covers {start} to {end}.")


# ------------------------------------------------------------------ incident KPIs

def sla_breach_rate(period: str = "last_quarter", group_by: str | None = "category", compare: bool = True,
                    service_id: str | None = None, con=None) -> dict:
    kind, value = resolve_period(period)
    _check_coverage(kind, value)
    prev = previous(kind, value)
    pcol = _period_col(kind)
    gcol = GROUPS.get(group_by or "", None)
    gsel = f"{gcol} AS grp," if gcol else "'All' AS grp,"
    where_svc = "AND service_id = :svc" if service_id else ""
    sql = f"""
        SELECT {gsel} {pcol} AS period,
               COUNT(*) AS incidents,
               SUM(sla_breached IS NOT NULL) AS outcome_known,
               SUM(COALESCE(sla_breached, 0)) AS breached
        FROM v_incidents
        WHERE {pcol} IN (:cur, :prev) {where_svc}
        GROUP BY grp, period"""
    df = db.query_df(sql, {"cur": value, "prev": prev, "svc": service_id}, con)
    df["breach_rate_pct"] = (100 * df.breached / df.outcome_known).round(1)
    cur = df[df.period == value].set_index("grp")
    out = cur[["incidents", "outcome_known", "breached", "breach_rate_pct"]].copy()
    if compare:
        pv = df[df.period == prev].set_index("grp")
        out["prev_breach_rate_pct"] = pv.breach_rate_pct.reindex(out.index)
        out["prev_breached"] = pv.breached.reindex(out.index)
        out["change_pp"] = (out.breach_rate_pct - out.prev_breach_rate_pct).round(1)
    out = out.sort_values("breach_rate_pct", ascending=False).reset_index().rename(columns={"grp": group_by or "scope"})
    top = out.iloc[0]
    summary = (f"In {value}, highest SLA breach rate: {top.iloc[0]} at {top.breach_rate_pct}% "
               f"({int(top.breached)} of {int(top.outcome_known)} incidents)")
    if compare and pd.notna(top.get("prev_breach_rate_pct")):
        summary += f", vs {top.prev_breach_rate_pct}% in {prev} ({top.change_pp:+.1f} pp)."
    return {"metric": "sla_breach_rate", "period": value, "compared_with": prev if compare else None,
            "definition": db.METRIC_DEFINITIONS["sla_breach_rate"], "data": _records(out), "summary": summary,
            "sql": _clean_sql(sql),
            "chart": {"type": "bar", "x": group_by or "scope", "y": ["breach_rate_pct", "prev_breach_rate_pct"] if compare else ["breach_rate_pct"],
                      "title": f"SLA breach rate % - {value} vs {prev}" if compare else f"SLA breach rate % - {value}"}}


def top_root_causes(period: str = "last_quarter", category: str | None = None, service_id: str | None = None,
                    rank_by: str = "incidents", compare: bool = True, limit: int = 8, con=None) -> dict:
    kind, value = resolve_period(period)
    _check_coverage(kind, value)
    prev = previous(kind, value)
    pcol = _period_col(kind)
    order = {"incidents": "incidents", "outage_minutes": "outage_minutes", "breaches": "breached"}[rank_by]
    filt, params = [], {"cur": value, "prev": prev}
    if category:
        filt.append("LOWER(category) = LOWER(:cat)")
        params["cat"] = category
    if service_id:
        filt.append("service_id = :svc")
        params["svc"] = service_id
    where = (" AND " + " AND ".join(filt)) if filt else ""
    sql = f"""
        SELECT root_cause, {pcol} AS period, COUNT(*) AS incidents,
               SUM(COALESCE(sla_breached,0)) AS breached, SUM(outage_minutes) AS outage_minutes,
               SUM(caused_outage) AS outages, ROUND(AVG(resolution_hours),1) AS mttr_hours
        FROM v_incidents WHERE {pcol} IN (:cur, :prev){where}
        GROUP BY root_cause, period"""
    df = db.query_df(sql, params, con)
    cur = df[df.period == value].set_index("root_cause").drop(columns="period")
    if compare:
        pv = df[df.period == prev].set_index("root_cause")
        cur[f"prev_{order}"] = pv[order].reindex(cur.index).fillna(0).astype(int)
        cur[f"change_{order}"] = cur[order] - cur[f"prev_{order}"]
    cur = cur.sort_values(order, ascending=False).head(limit).reset_index()
    scope = category or service_id or "all services"
    top = cur.iloc[0] if len(cur) else None
    summary = (f"Top root cause by {rank_by} in {value} ({scope}): {top.root_cause} with {int(top[order])}"
               + (f" (vs {int(top[f'prev_{order}'])} in {prev})" if compare else "") + ".") if top is not None else "No incidents."
    return {"metric": f"root_causes_by_{rank_by}", "period": value, "scope": scope, "data": _records(cur), "summary": summary,
            "sql": _clean_sql(sql), "chart": {"type": "bar", "x": "root_cause", "y": [order], "title": f"Root causes by {rank_by} - {value} ({scope})"}}


def downtime_causes(months: int = 6, limit: int = 8, con=None) -> dict:
    """Recurring causes of customer-facing downtime over the trailing window."""
    end = pd.Period(config.SNAPSHOT_DATE, freq="M")
    start = str(end - (months - 1))
    sql = """
        SELECT root_cause, COUNT(*) AS outages, SUM(outage_minutes) AS outage_minutes,
               COUNT(DISTINCT opened_month) AS months_present, COUNT(DISTINCT service_id) AS services_affected,
               GROUP_CONCAT(DISTINCT service_name) AS services
        FROM v_incidents WHERE caused_outage = 1 AND opened_month >= :start
        GROUP BY root_cause ORDER BY outage_minutes DESC LIMIT :lim"""
    df = db.query_df(sql, {"start": start, "lim": limit}, con)
    total = db.query_df("SELECT SUM(outage_minutes) AS m FROM incidents WHERE caused_outage=1 AND opened_month >= :start",
                        {"start": start}, con).m.iloc[0]
    df["share_of_downtime_pct"] = (100 * df.outage_minutes / total).round(1)
    df["recurring"] = df.months_present >= max(3, months // 2)
    top = df.iloc[0]
    return {"metric": "downtime_by_root_cause", "window": f"{start} to {end}", "total_outage_minutes": int(total),
            "data": _records(df), "sql": _clean_sql(sql),
            "summary": f"{top.root_cause} caused the most downtime from {start} to {end}: {int(top.outage_minutes)} minutes "
                       f"({top.share_of_downtime_pct}% of {int(total)}) across {int(top.outages)} outages.",
            "chart": {"type": "bar", "x": "root_cause", "y": ["outage_minutes"], "title": f"Downtime minutes by root cause, {start} to {end}"}}


def incident_trend(group_by: str | None = None, months: int = 18, con=None) -> dict:
    gcol = GROUPS.get(group_by or "")
    sel = f"{gcol} AS grp," if gcol else ""
    grp = "grp," if gcol else ""
    sql = f"""
        SELECT {sel} opened_month AS month, COUNT(*) AS incidents,
               ROUND(100.0*SUM(COALESCE(sla_breached,0))/SUM(sla_breached IS NOT NULL),1) AS breach_rate_pct,
               ROUND(AVG(resolution_hours),2) AS mttr_hours, SUM(outage_minutes) AS outage_minutes
        FROM v_incidents GROUP BY {grp} month ORDER BY month"""
    df = db.query_df(sql, (), con)
    df = df[df.month >= str(pd.Period(config.SNAPSHOT_DATE, freq="M") - (months - 1))]
    return {"metric": "incident_trend", "data": _records(df), "sql": _clean_sql(sql), "summary": f"{len(df)} monthly rows.",
            "chart": {"type": "line", "x": "month", "y": ["incidents"], "color": "grp" if gcol else None, "title": "Monthly incidents"}}


def backlog(con=None) -> dict:
    snap = f"{config.SNAPSHOT_DATE.isoformat()} 23:59:59"
    sql = """
        SELECT service_name, business_unit, COUNT(*) AS open_incidents,
               SUM(sla_breached = 1) AS open_past_target,
               ROUND(AVG((julianday(:snap) - julianday(opened_at))*24),1) AS avg_age_hours
        FROM v_incidents WHERE resolved_at IS NULL
        GROUP BY service_name, business_unit ORDER BY open_past_target DESC, open_incidents DESC"""
    df = db.query_df(sql, {"snap": snap}, con)
    top = df.iloc[0]
    return {"metric": "open_incident_backlog", "as_of": config.SNAPSHOT_DATE.isoformat(), "data": _records(df), "sql": _clean_sql(sql),
            "summary": f"{int(df.open_incidents.sum())} open incidents at snapshot; {int(df.open_past_target.sum())} already past SLA target "
                       f"(most: {top.service_name}, {int(top.open_past_target)}).",
            "chart": {"type": "bar", "x": "service_name", "y": ["open_incidents", "open_past_target"], "title": "Open incident backlog"}}


# ------------------------------------------------------------------ costs

def cost_change(month: str = "this_month", group_by: str = "service_cost_type", limit: int = 8, con=None) -> dict:
    kind, value = resolve_period(month)
    if kind != "month":
        raise ValueError("cost_change works on months (YYYY-MM or this_month).")
    _check_coverage(kind, value)
    prev = previous(kind, value)
    sql = """
        SELECT c.month, s.name AS service, b.name AS business_unit, c.cost_type, c.amount_gbp, c.description
        FROM costs c JOIN services s USING (service_id) JOIN business_units b ON b.bu_id = s.bu_id
        WHERE c.month IN (:cur, :prev)"""
    df = db.query_df(sql, {"cur": value, "prev": prev}, con)
    keys = {"service_cost_type": ["service", "cost_type"], "service": ["service"], "cost_type": ["cost_type"],
            "business_unit": ["business_unit"]}[group_by]
    piv = df.pivot_table(index=keys, columns="month", values="amount_gbp", aggfunc="sum").fillna(0)
    piv.columns = [str(c) for c in piv.columns]
    piv = piv.rename(columns={value: "current_gbp", prev: "previous_gbp"})
    piv["change_gbp"] = (piv.current_gbp - piv.previous_gbp).round(2)
    piv["change_pct"] = (100 * piv.change_gbp / piv.previous_gbp).round(1)
    desc = df[df.month == value].groupby(keys).description.apply(lambda s: "; ".join(sorted(set(s)))) if group_by == "service_cost_type" else None
    if desc is not None:
        piv["ledger_narrative"] = desc
    total_cur, total_prev = df[df.month == value].amount_gbp.sum(), df[df.month == prev].amount_gbp.sum()
    drivers = piv.sort_values("change_gbp", ascending=False).head(limit).reset_index()
    for c in ("current_gbp", "previous_gbp"):
        drivers[c] = drivers[c].round(2)
    delta = total_cur - total_prev
    top3 = drivers.head(3).change_gbp.sum()
    return {
        "metric": "operating_cost_change", "month": value, "compared_with": prev,
        "total_current_gbp": round(total_cur, 2), "total_previous_gbp": round(total_prev, 2),
        "total_change_gbp": round(delta, 2), "total_change_pct": round(100 * delta / total_prev, 1),
        "top3_drivers_share_of_change_pct": round(100 * top3 / delta, 1) if delta else None,
        "data": _records(drivers), "sql": _clean_sql(sql),
        "summary": f"Operating cost {value}: £{total_cur:,.0f} vs £{total_prev:,.0f} in {prev} ({delta:+,.0f}, {100 * delta / total_prev:+.1f}%). "
                   f"Largest increase: {' / '.join(str(v) for v in drivers.iloc[0][keys])} {drivers.iloc[0].change_gbp:+,.0f}.",
        "chart": {"type": "bar", "x": keys[0], "y": ["change_gbp"], "title": f"Cost change by {group_by.replace('_', ' ')}: {value} vs {prev}"},
    }


def cost_trend(group_by: str = "business_unit", con=None) -> dict:
    sql = """
        SELECT c.month, b.name AS business_unit, c.cost_type, SUM(c.amount_gbp) AS amount_gbp
        FROM costs c JOIN services s USING (service_id) JOIN business_units b ON b.bu_id = s.bu_id
        GROUP BY c.month, b.name, c.cost_type ORDER BY c.month"""
    df = db.query_df(sql, (), con)
    df = df.groupby(["month", group_by], as_index=False).amount_gbp.sum().round(2)
    return {"metric": "cost_trend", "data": _records(df), "sql": _clean_sql(sql), "summary": f"{df.month.nunique()} months of cost data.",
            "chart": {"type": "area", "x": "month", "y": ["amount_gbp"], "color": group_by, "title": "Monthly operating cost (GBP)"}}


# ------------------------------------------------------------------ requests / delivery

def delivery_performance(period: str = "last_quarter", con=None) -> dict:
    kind, value = resolve_period(period)
    _check_coverage(kind, value)
    expr = "strftime('%Y', closed_at) || 'Q' || ((CAST(strftime('%m', closed_at) AS INT)+2)/3)" if kind == "quarter" else "strftime('%Y-%m', closed_at)"
    sql = f"""
        SELECT s.name AS service, r.request_type, COUNT(*) AS closed,
               SUM(r.met_due_date) AS on_time, ROUND(100.0*SUM(r.met_due_date)/COUNT(*),1) AS on_time_pct,
               ROUND(AVG(r.fulfilment_days),1) AS avg_days, MAX(r.target_days) AS target_days
        FROM service_requests r JOIN services s USING (service_id)
        WHERE r.closed_at IS NOT NULL AND {expr} = :p
        GROUP BY s.name, r.request_type ORDER BY on_time_pct ASC"""
    df = db.query_df(sql, {"p": value}, con)
    worst = df.iloc[0]
    return {"metric": "on_time_delivery_rate", "period": value, "data": _records(df), "sql": _clean_sql(sql),
            "summary": f"Lowest on-time delivery in {value}: {worst.request_type} ({worst.service}) at {worst.on_time_pct}% of {int(worst.closed)}.",
            "chart": {"type": "bar", "x": "request_type", "y": ["on_time_pct"], "title": f"On-time delivery % by request type - {value}"}}


# ------------------------------------------------------------------ prioritisation

def improvement_priorities(period: str = "last_quarter", con=None) -> dict:
    """Rank process areas by customer-impact excess: hours beyond SLA target (incident
    management, per category) and days beyond due date (request fulfilment, per type)."""
    kind, value = resolve_period(period)
    _check_coverage(kind, value)
    pcol = _period_col(kind)
    q_inc = f"""
        SELECT 'Incident management' AS process, category AS area, COUNT(*) AS volume,
               SUM(COALESCE(sla_breached,0)) AS failures,
               ROUND(SUM(MAX(COALESCE(resolution_hours,0) - sla_target_hours, 0)),1) AS excess_hours,
               SUM(outage_minutes) AS outage_minutes
        FROM incidents WHERE {pcol} = :p GROUP BY category"""
    expr = "strftime('%Y', opened_at) || 'Q' || ((CAST(strftime('%m', opened_at) AS INT)+2)/3)" if kind == "quarter" else "strftime('%Y-%m', opened_at)"
    q_req = f"""
        SELECT 'Request fulfilment' AS process, request_type AS area, COUNT(*) AS volume,
               SUM(met_due_date = 0) AS failures,
               ROUND(24*SUM(MAX(COALESCE(fulfilment_days,0) - target_days, 0)),1) AS excess_hours,
               0 AS outage_minutes
        FROM service_requests WHERE {expr} = :p GROUP BY request_type"""
    df = pd.concat([db.query_df(q_inc, {"p": value}, con), db.query_df(q_req, {"p": value}, con)], ignore_index=True)
    df["failure_rate_pct"] = (100 * df.failures / df.volume).round(1)
    # Score: excess hours share + downtime share (equal weights; documented and tunable).
    df["impact_score"] = (50 * df.excess_hours / df.excess_hours.sum() + 50 * df.outage_minutes / max(1, df.outage_minutes.sum())).round(1)
    df = df.sort_values("impact_score", ascending=False).head(10).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    top = df.iloc[0]
    return {"metric": "improvement_priorities", "period": value,
            "method": "impact_score = 50 x share of hours beyond SLA/due date + 50 x share of downtime minutes",
            "data": _records(df), "sql": _clean_sql(q_inc + ";\n" + q_req),
            "summary": f"Highest-impact improvement area in {value}: {top.process} - {top.area} (score {top.impact_score}, "
                       f"{int(top.failures)} failures of {int(top.volume)}, {top.excess_hours:,.0f} excess hours).",
            "chart": {"type": "bar", "x": "area", "y": ["impact_score"], "title": f"Improvement priority score - {value}"}}


def headline_kpis(con=None) -> dict:
    snap_m = config.SNAPSHOT_DATE.strftime("%Y-%m")
    prev_m = _shift_month(snap_m, -1)
    sql = """
        SELECT opened_month AS month, COUNT(*) AS incidents,
               ROUND(100.0*SUM(COALESCE(sla_breached,0))/SUM(sla_breached IS NOT NULL),1) AS breach_rate_pct,
               ROUND(AVG(resolution_hours),2) AS mttr_hours, SUM(outage_minutes) AS outage_minutes
        FROM incidents WHERE opened_month IN (:m, :p) GROUP BY opened_month"""
    df = db.query_df(sql, {"m": snap_m, "p": prev_m}, con).set_index("month")
    cost = db.query_df("SELECT month, SUM(amount_gbp) AS cost FROM costs WHERE month IN (:m,:p) GROUP BY month",
                       {"m": snap_m, "p": prev_m}, con).set_index("month").cost
    open_inc = db.query_df("SELECT COUNT(*) AS n FROM incidents WHERE resolved_at IS NULL", (), con).n.iloc[0]
    out = {"month": snap_m, "previous_month": prev_m, "open_incidents": int(open_inc)}

    def val(frame_or_series, month, col=None):
        try:
            x = frame_or_series.loc[month, col] if col else frame_or_series[month]
            return None if pd.isna(x) else round(float(x), 2)
        except KeyError:
            return None   # no data for that month (e.g. a source without costs)

    for k in ("incidents", "breach_rate_pct", "mttr_hours", "outage_minutes"):
        out[k], out[f"{k}_prev"] = val(df, snap_m, k), val(df, prev_m, k)
    out["cost_gbp"], out["cost_gbp_prev"] = val(cost, snap_m), val(cost, prev_m)
    return out


def _records(df: pd.DataFrame) -> list[dict]:
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_integer_dtype(df[c]):
            df[c] = df[c].astype(object)
    return [{k: (None if (isinstance(v, float) and pd.isna(v)) else (v.item() if hasattr(v, "item") else v))
             for k, v in r.items()} for r in df.to_dict("records")]


def _clean_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()
