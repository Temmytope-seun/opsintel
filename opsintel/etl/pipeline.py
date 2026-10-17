"""ETL: four source systems -> validated, unified operational store with lineage.

    python -m opsintel.etl.pipeline
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from opsintel import config, db
from opsintel.etl import connectors
from opsintel.etl.quality import EntityMatcher, Rules, parse_datetime, profile

PRIORITY_MATRIX = {
    (1, 1): "P1", (1, 2): "P2", (2, 1): "P2", (1, 3): "P3", (2, 2): "P3",
    (3, 1): "P3", (2, 3): "P4", (3, 2): "P4", (3, 3): "P4",
}
SEVERITIES = {"critical", "major", "minor", "warning"}


class Run:
    def __init__(self, con):
        self.con = con
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
        self.report: dict[str, dict] = {}
        con.execute("INSERT INTO etl_runs VALUES (?,?,?,?)", (self.run_id, _now(), None, "running"))

    def reject(self, source: str, rows: pd.DataFrame, key: str, reason: str):
        if rows.empty:
            return
        self.con.executemany(
            "INSERT INTO etl_rejects VALUES (?,?,?,?,?)",
            [(self.run_id, source, str(r.get(key)), reason, json.dumps(r, default=str)) for r in rows.to_dict("records")],
        )
        self.report.setdefault(source, {}).setdefault("rejects", {})[reason] = len(rows)

    def dq(self, source: str, stage: str, metrics: dict):
        self.con.executemany("INSERT INTO dq_results VALUES (?,?,?,?,?)",
                             [(self.run_id, source, stage, k, float(v)) for k, v in metrics.items()])
        self.report.setdefault(source, {})[stage] = metrics

    def lineage(self, target, source_name, prov, rows_in, rows_out, rejected, transforms):
        self.con.execute(
            "INSERT INTO lineage VALUES (?,?,?,?,?,?,?,?,?,?)",
            (self.run_id, target, source_name, prov["source_type"], prov["source_uri"], prov.get("source_sha256"),
             rows_in, rows_out, rejected, json.dumps(transforms)))


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _iso(s: pd.Series) -> pd.Series:
    return s.dt.strftime("%Y-%m-%d %H:%M:%S").where(s.notna(), None)


def _load(con, table: str, df: pd.DataFrame):
    con.execute(f"DELETE FROM {table}")
    _insert(con, table, df)


def _insert(con, table: str, df: pd.DataFrame):
    cols = list(df.columns)
    df = df.astype(object).where(df.notna(), None)
    con.executemany(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                    df.itertuples(index=False, name=None))


# ------------------------------------------------------------------ reference (CMDB)

def load_reference(run: Run):
    con = run.con
    out = {}
    for target, table in [("business_units", "cmdb_business_unit"), ("services", "cmdb_service"),
                          ("sla_policies", "sla_definition"), ("customers", "core_company"), ("assets", "cmdb_ci")]:
        df, prov = connectors.read_sql_table(config.CMDB_PATH, table)
        key = df.columns[0]
        rules = Rules(key=[key], required=[key])
        run.dq(target, "before", profile(df, rules))
        clean = df.drop_duplicates(subset=[key])
        if target == "services":
            out["aliases"] = {r.service_id: r.aliases.split("|") for r in clean.itertuples()}
            clean = clean.drop(columns=["aliases"])
        if target == "assets":
            bad = clean[~clean.service_id.isin(out["services"].service_id)]
            run.reject(target, bad, key, "unknown_service")
            clean = clean[clean.service_id.isin(out["services"].service_id)]
        _insert(con, target, clean)
        run.dq(target, "after", profile(clean, rules))
        run.lineage(target, f"CMDB.{table}", prov, len(df), len(clean), len(df) - len(clean),
                    ["read_only_extract", "dedupe_on_primary_key"])
        out[target] = clean
    return out


def _matcher(ref) -> EntityMatcher:
    svc = ref["services"]
    return EntityMatcher(dict(zip(svc.service_id, svc.name)), ref["aliases"])


# ------------------------------------------------------------------ incidents (ITSM CSV)

def load_incidents(run: Run, ref):
    src = "incidents"
    raw, prov = connectors.read_csv(config.RAW_DIR / "itsm_incidents.csv")
    svc_names = set(ref["services"].name)
    rules_before = Rules(key=["incident_id"], required=["incident_id", "opened_at", "service", "priority", "customer_id"],
                         iso_dates=["opened_at", "resolved_at"], enums={"priority": {"P1", "P2", "P3", "P4"}},
                         refs={"service": svc_names, "customer_id": set(ref["customers"].customer_id)})
    run.dq(src, "before", profile(raw, rules_before))
    steps = []
    df = raw.copy()
    for c in df.columns:
        df[c] = df[c].str.strip()
    steps.append("trim_whitespace")
    for c in ("opened_at", "resolved_at", "sys_updated_on"):
        df[c] = parse_datetime(df[c])
    steps.append("parse_datetimes(iso8601|dd/mm/yyyy)")

    n0 = len(df)
    df = df.drop_duplicates()
    steps.append(f"drop_exact_duplicates({n0 - len(df)})")
    n1 = len(df)
    df = df.sort_values("sys_updated_on").drop_duplicates("incident_id", keep="last")
    steps.append(f"keep_latest_version_per_incident({n1 - len(df)})")

    m = _matcher(ref)
    df["service_id"] = [m.match(v) for v in df.service]
    steps.append(f"entity_match_service({m.stats})")
    run.report.setdefault(src, {})["entity_matching"] = dict(m.stats)

    is_test = df.short_description.str.contains(r"\bTEST TICKET\b", case=False, na=False)
    run.reject(src, df[is_test], "incident_id", "test_record")
    df = df[~is_test]
    bad_time = df.opened_at.isna() | (df.resolved_at.notna() & (df.resolved_at < df.opened_at))
    run.reject(src, df[bad_time], "incident_id", "invalid_timestamps")
    df = df[~bad_time]
    orphan = ~df.customer_id.isin(ref["customers"].customer_id)
    run.reject(src, df[orphan], "incident_id", "orphan_customer")
    df = df[~orphan]
    unmatched = df.service_id.isna()
    run.reject(src, df[unmatched], "incident_id", "unmatched_service")
    df = df[~unmatched]
    steps.append("reject(test_record|invalid_timestamps|orphan_customer|unmatched_service)")

    df["impact"] = df.impact.astype(int)
    df["urgency"] = df.urgency.astype(int)
    missing_p = df.priority.eq("") | df.priority.isna()
    df.loc[missing_p, "priority"] = [PRIORITY_MATRIX[(i, u)] for i, u in zip(df.impact[missing_p], df.urgency[missing_p])]
    df["priority_imputed"] = missing_p.astype(int)
    steps.append(f"impute_priority_from_impact_urgency({int(missing_p.sum())})")

    svc = ref["services"].set_index("service_id")
    sla = ref["sla_policies"].set_index("priority").resolution_target_hrs
    df["category"] = df.service_id.map(svc.category)
    df["sla_target_hours"] = df.priority.map(sla).astype(float)
    snap_end = pd.Timestamp(config.SNAPSHOT_DATE) + pd.Timedelta(days=1)
    df["resolution_hours"] = ((df.resolved_at - df.opened_at).dt.total_seconds() / 3600).round(3)
    elapsed = (snap_end - df.opened_at).dt.total_seconds() / 3600
    breached = np.where(df.resolved_at.notna(), df.resolution_hours > df.sla_target_hours,
                        np.where(elapsed > df.sla_target_hours, True, np.nan))
    df["sla_breached"] = pd.array([None if pd.isna(b) else int(b) for b in breached], dtype="Int64")
    df["opened_month"] = df.opened_at.dt.strftime("%Y-%m")
    df["opened_quarter"] = df.opened_at.dt.to_period("Q").astype(str)
    for c in ("caused_outage", "reopened"):
        df[c] = df[c].map({"True": 1, "False": 0}).fillna(0).astype(int)
    df["outage_minutes"] = pd.to_numeric(df.outage_minutes).fillna(0).astype(int)
    steps.append("derive(category, resolution_hours, sla_target_hours, sla_breached, opened_month, opened_quarter)")
    df["opened_at"], df["resolved_at"] = _iso(df.opened_at), _iso(df.resolved_at)
    df["asset_id"] = df.asset_id.replace("", None)

    cols = ["incident_id", "opened_at", "resolved_at", "status", "service_id", "customer_id", "asset_id", "impact",
            "urgency", "priority", "priority_imputed", "category", "assignment_group", "root_cause", "short_description",
            "caused_outage", "outage_minutes", "reopened", "resolution_hours", "sla_target_hours", "sla_breached",
            "opened_month", "opened_quarter"]
    clean = df[cols].sort_values("incident_id")
    _load(run.con, "incidents", clean)
    rules_after = Rules(key=["incident_id"], required=["incident_id", "opened_at", "service_id", "priority", "customer_id"],
                        iso_dates=["opened_at", "resolved_at"], enums={"priority": {"P1", "P2", "P3", "P4"}},
                        refs={"service_id": set(svc.index), "customer_id": set(ref["customers"].customer_id)})
    run.dq(src, "after", profile(clean, rules_after))
    run.lineage("incidents", "ITSM incident export", prov, len(raw), len(clean), len(raw) - len(clean), steps)


# ------------------------------------------------------------------ requests (ITSM CSV)

def load_requests(run: Run, ref):
    src = "service_requests"
    raw, prov = connectors.read_csv(config.RAW_DIR / "itsm_requests.csv")
    rules_before = Rules(key=["request_id"], required=["request_id", "opened_at", "due_at", "service"],
                         iso_dates=["opened_at", "due_at", "closed_at"], refs={"service": set(ref["services"].name)})
    run.dq(src, "before", profile(raw, rules_before))
    steps = ["trim_whitespace"]
    df = raw.apply(lambda c: c.str.strip())
    for c in ("opened_at", "due_at", "closed_at"):
        df[c] = parse_datetime(df[c])
    steps.append("parse_datetimes(iso8601|dd/mm/yyyy)")
    n0 = len(df)
    df = df.drop_duplicates().drop_duplicates("request_id", keep="last")
    steps.append(f"drop_duplicates({n0 - len(df)})")
    m = _matcher(ref)
    df["service_id"] = [m.match(v) for v in df.service]
    steps.append(f"entity_match_service({m.stats})")
    run.report.setdefault(src, {})["entity_matching"] = dict(m.stats)
    unmatched = df.service_id.isna()
    run.reject(src, df[unmatched], "request_id", "unmatched_service")
    df = df[~unmatched]
    df["target_days"] = df.target_days.astype(float)
    df["blocked_reason"] = df.blocked_reason.replace("", None)
    df["fulfilment_days"] = ((df.closed_at - df.opened_at).dt.total_seconds() / 86400).round(3)
    df["met_due_date"] = pd.array([None if pd.isna(c) else int(c <= d) for c, d in zip(df.closed_at, df.due_at)], dtype="Int64")
    steps.append("derive(fulfilment_days, met_due_date)")
    for c in ("opened_at", "due_at", "closed_at"):
        df[c] = _iso(df[c])
    cols = ["request_id", "opened_at", "due_at", "closed_at", "status", "service_id", "customer_id", "request_type",
            "target_days", "blocked_reason", "assignment_group", "fulfilment_days", "met_due_date"]
    clean = df[cols].sort_values("request_id")
    _load(run.con, "service_requests", clean)
    run.dq(src, "after", profile(clean, Rules(key=["request_id"], required=["request_id", "opened_at", "due_at", "service_id"],
                                              iso_dates=["opened_at", "due_at", "closed_at"],
                                              refs={"service_id": set(ref["services"].service_id)})))
    run.lineage("service_requests", "ITSM requested-item export", prov, len(raw), len(clean), len(raw) - len(clean), steps)


# ------------------------------------------------------------------ alerts (REST API)

def load_alerts(run: Run, ref):
    src = "alerts"
    raw, prov = connectors.read_rest_paginated()
    raw = raw.astype({"value": float})
    rules = Rules(key=["alert_id"], required=["alert_id", "ts", "asset_id", "severity"], iso_dates=["ts"],
                  enums={"severity": SEVERITIES}, refs={"asset_id": set(ref["assets"].asset_id)})
    run.dq(src, "before", profile(raw.astype({"value": str}), rules))
    df = raw.drop_duplicates("alert_id")
    steps = [f"dedupe_at_least_once_delivery({len(raw) - len(df)})"]
    df["severity"] = df.severity.str.lower()
    steps.append("normalise_severity_case")
    df["ts"] = _iso(pd.to_datetime(df.ts, format="ISO8601"))
    df = df.merge(ref["assets"][["asset_id", "service_id"]], on="asset_id", how="left")
    orphan = df.service_id.isna()
    run.reject(src, df[orphan], "alert_id", "unknown_asset")
    df = df[~orphan]
    steps.append("enrich_service_via_cmdb_asset")
    clean = df[["alert_id", "ts", "asset_id", "service_id", "severity", "metric", "value"]]
    _load(run.con, "alerts", clean)
    run.dq(src, "after", profile(clean, Rules(key=["alert_id"], required=["alert_id", "ts", "asset_id", "severity"],
                                              iso_dates=["ts"], enums={"severity": SEVERITIES},
                                              refs={"asset_id": set(ref["assets"].asset_id)})))
    run.lineage("alerts", "Monitoring REST API", prov, len(raw), len(clean), len(raw) - len(clean), steps)


# ------------------------------------------------------------------ costs (finance CSV)

def load_costs(run: Run, ref):
    src = "costs"
    raw, prov = connectors.read_csv(config.RAW_DIR / "finance_costs.csv")
    rules_before = Rules(key=["month", "service_id", "cost_type"], required=["month", "service_id", "amount"],
                         patterns={"month": r"\d{4}-\d{2}"}, numeric=["amount"], refs={"service_id": set(ref["services"].service_id)})
    run.dq(src, "before", profile(raw, rules_before))
    df = raw.drop_duplicates().copy()
    steps = [f"drop_exact_duplicates({len(raw) - len(df)})"]
    df["month"] = [pd.to_datetime(m, format="%b-%Y").strftime("%Y-%m") if "-" in m and m[:3].isalpha() else m
                   for m in df.month]
    steps.append("normalise_month(Mon-YYYY -> YYYY-MM)")
    df["amount_gbp"] = df.amount.str.replace(r"[£,\s]", "", regex=True).astype(float)
    steps.append("parse_currency")
    dup_key = df.duplicated(["month", "service_id", "cost_type"], keep="last")
    run.reject(src, df[dup_key], "month", "duplicate_ledger_line")
    df = df[~dup_key]
    clean = df[["month", "service_id", "cost_type", "amount_gbp", "description"]]
    _load(run.con, "costs", clean)
    run.dq(src, "after", profile(clean, Rules(key=["month", "service_id", "cost_type"], required=["month", "service_id", "amount_gbp"],
                                              patterns={"month": r"\d{4}-\d{2}"}, numeric=["amount_gbp"], refs={"service_id": set(ref["services"].service_id)})))
    run.lineage("costs", "Finance ledger export", prov, len(raw), len(clean), len(raw) - len(clean), steps)


def run_pipeline(db_path=None) -> dict:
    db_path = db_path or config.DB_PATH
    with db.session(db_path) as con:
        db.init_schema(con)
        run = Run(con)
        # Child tables first, so FK constraints hold during reload.
        for t in ("alerts", "incidents", "service_requests", "costs", "assets", "services", "customers",
                  "sla_policies", "business_units"):
            con.execute(f"DELETE FROM {t}")
        ref = load_reference(run)
        load_incidents(run, ref)
        load_requests(run, ref)
        load_alerts(run, ref)
        load_costs(run, ref)
        from opsintel.governance.rbac import seed_users

        seed_users(con)
        con.execute("UPDATE etl_runs SET finished_at=?, status='succeeded' WHERE run_id=?", (_now(), run.run_id))
        fk_errors = con.execute("PRAGMA foreign_key_check").fetchall()
        run.report["_run"] = {"run_id": run.run_id, "foreign_key_violations": len(fk_errors)}
    return run.report


def main():
    report = run_pipeline()
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
