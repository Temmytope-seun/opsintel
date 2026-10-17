"""Unified data foundation: schema, metadata catalogue and connection helpers.

SQLite keeps the MVP dependency-free. Everything here is standard SQL apart from the
read-only authorizer in ai/sql_guard.py; docs/architecture.md describes the PostgreSQL
mapping (read-only role + row-level security + pgvector).
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from opsintel import config

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS business_units (
    bu_id TEXT PRIMARY KEY,
    name  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS services (
    service_id  TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    bu_id       TEXT NOT NULL REFERENCES business_units(bu_id),
    tier        TEXT NOT NULL,
    owner_group TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sla_policies (
    priority              TEXT PRIMARY KEY,
    label                 TEXT NOT NULL,
    response_target_hrs   REAL NOT NULL,
    resolution_target_hrs REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS customers (
    customer_id        TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    sector             TEXT,
    contact_email      TEXT,
    contact_phone      TEXT,
    contract_value_gbp INTEGER,
    account_manager    TEXT
);
CREATE TABLE IF NOT EXISTS assets (
    asset_id         TEXT PRIMARY KEY,
    service_id       TEXT NOT NULL REFERENCES services(service_id),
    asset_type       TEXT NOT NULL,
    vendor           TEXT,
    install_date     TEXT,
    status           TEXT,
    location         TEXT,
    firmware_version TEXT
);
CREATE TABLE IF NOT EXISTS incidents (
    incident_id       TEXT PRIMARY KEY,
    opened_at         TEXT NOT NULL,
    resolved_at       TEXT,
    status            TEXT NOT NULL,
    service_id        TEXT NOT NULL REFERENCES services(service_id),
    customer_id       TEXT NOT NULL REFERENCES customers(customer_id),
    asset_id          TEXT REFERENCES assets(asset_id),
    impact            INTEGER CHECK (impact BETWEEN 1 AND 3),
    urgency           INTEGER CHECK (urgency BETWEEN 1 AND 3),
    priority          TEXT NOT NULL REFERENCES sla_policies(priority),
    priority_imputed  INTEGER NOT NULL DEFAULT 0,
    category          TEXT NOT NULL,
    assignment_group  TEXT,
    root_cause        TEXT,
    short_description TEXT,
    caused_outage     INTEGER NOT NULL DEFAULT 0,
    outage_minutes    INTEGER NOT NULL DEFAULT 0,
    reopened          INTEGER NOT NULL DEFAULT 0,
    resolution_hours  REAL,
    sla_target_hours  REAL NOT NULL,
    sla_breached      INTEGER,          -- NULL = open and still inside target (undetermined)
    opened_month      TEXT NOT NULL,    -- YYYY-MM
    opened_quarter    TEXT NOT NULL     -- YYYYQn
);
CREATE INDEX IF NOT EXISTS ix_inc_service ON incidents(service_id, opened_at);
CREATE INDEX IF NOT EXISTS ix_inc_quarter ON incidents(opened_quarter, category);

CREATE TABLE IF NOT EXISTS service_requests (
    request_id       TEXT PRIMARY KEY,
    opened_at        TEXT NOT NULL,
    due_at           TEXT NOT NULL,
    closed_at        TEXT,
    status           TEXT NOT NULL,
    service_id       TEXT NOT NULL REFERENCES services(service_id),
    customer_id      TEXT NOT NULL REFERENCES customers(customer_id),
    request_type     TEXT NOT NULL,
    target_days      REAL NOT NULL,
    blocked_reason   TEXT,
    assignment_group TEXT,
    fulfilment_days  REAL,
    met_due_date     INTEGER          -- NULL while open
);
CREATE TABLE IF NOT EXISTS alerts (
    alert_id   TEXT PRIMARY KEY,
    ts         TEXT NOT NULL,
    asset_id   TEXT NOT NULL REFERENCES assets(asset_id),
    service_id TEXT NOT NULL REFERENCES services(service_id),
    severity   TEXT NOT NULL CHECK (severity IN ('critical','major','minor','warning')),
    metric     TEXT,
    value      REAL
);
CREATE INDEX IF NOT EXISTS ix_alert_service ON alerts(service_id, ts);
CREATE TABLE IF NOT EXISTS costs (
    month       TEXT NOT NULL,
    service_id  TEXT NOT NULL REFERENCES services(service_id),
    cost_type   TEXT NOT NULL,
    amount_gbp  REAL NOT NULL,
    description TEXT,
    PRIMARY KEY (month, service_id, cost_type)
);

-- PII-free projection used by the AI layer and most roles.
CREATE VIEW IF NOT EXISTS customers_safe AS
    SELECT customer_id, name, sector, contract_value_gbp FROM customers;

CREATE VIEW IF NOT EXISTS v_incidents AS
    SELECT i.*, s.name AS service_name, s.bu_id, b.name AS business_unit, s.tier
    FROM incidents i JOIN services s USING (service_id) JOIN business_units b USING (bu_id);

-- ---------------------------------------------------------------- lineage & quality
CREATE TABLE IF NOT EXISTS etl_runs (
    run_id      TEXT PRIMARY KEY,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lineage (
    run_id        TEXT NOT NULL REFERENCES etl_runs(run_id),
    target_table  TEXT NOT NULL,
    source_name   TEXT NOT NULL,
    source_type   TEXT NOT NULL,
    source_uri    TEXT NOT NULL,
    source_sha256 TEXT,
    rows_in       INTEGER NOT NULL,
    rows_out      INTEGER NOT NULL,
    rows_rejected INTEGER NOT NULL,
    transforms    TEXT NOT NULL      -- JSON list of applied steps
);
CREATE TABLE IF NOT EXISTS etl_rejects (
    run_id     TEXT NOT NULL,
    source     TEXT NOT NULL,
    record_key TEXT,
    reason     TEXT NOT NULL,
    payload    TEXT
);
CREATE TABLE IF NOT EXISTS dq_results (
    run_id  TEXT NOT NULL,
    source  TEXT NOT NULL,
    stage   TEXT NOT NULL CHECK (stage IN ('before','after')),
    metric  TEXT NOT NULL,
    value   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS catalog (
    table_name  TEXT NOT NULL,
    column_name TEXT NOT NULL,
    description TEXT NOT NULL,
    is_pii      INTEGER NOT NULL DEFAULT 0,
    source      TEXT,
    PRIMARY KEY (table_name, column_name)
);

-- ---------------------------------------------------------------- governance
CREATE TABLE IF NOT EXISTS users (
    user_id   TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    role      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    role       TEXT NOT NULL,
    event      TEXT NOT NULL,
    detail     TEXT NOT NULL,      -- JSON
    prev_hash  TEXT NOT NULL,
    hash       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS actions (
    action_id    TEXT PRIMARY KEY,
    created_at   TEXT NOT NULL,
    created_by   TEXT NOT NULL,
    title        TEXT NOT NULL,
    rationale    TEXT NOT NULL,
    evidence     TEXT NOT NULL,     -- JSON list of evidence records
    service_id   TEXT,
    owner_group  TEXT,
    priority     TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('proposed','approved','rejected','in_progress','done')),
    decided_by   TEXT,
    decided_at   TEXT,
    decision_note TEXT,
    outcome      TEXT
);
CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    channel    TEXT NOT NULL,
    recipient  TEXT NOT NULL,
    subject    TEXT NOT NULL,
    body       TEXT NOT NULL,
    delivered  INTEGER NOT NULL DEFAULT 0
);
"""

# Business-facing descriptions, PII flags and provenance. Rendered into
# docs/data_dictionary.md and exposed to the assistant so it can describe the data.
CATALOG: dict[str, dict[str, tuple[str, bool, str]]] = {
    "services": {
        "service_id": ("Service code (CMDB)", False, "CMDB.cmdb_service"),
        "name": ("Canonical service name", False, "CMDB.cmdb_service"),
        "category": ("Service category used for SLA reporting (Network, Cloud, ...)", False, "CMDB.cmdb_service"),
        "bu_id": ("Owning business unit", False, "CMDB.cmdb_service"),
        "tier": ("Commercial service tier", False, "CMDB.cmdb_service"),
        "owner_group": ("Resolver group that owns the service", False, "CMDB.cmdb_service"),
    },
    "customers": {
        "customer_id": ("Customer account code", False, "CMDB.core_company"),
        "name": ("Customer organisation name", False, "CMDB.core_company"),
        "sector": ("Industry sector", False, "CMDB.core_company"),
        "contact_email": ("Named operational contact e-mail", True, "CMDB.core_company"),
        "contact_phone": ("Named operational contact phone", True, "CMDB.core_company"),
        "contract_value_gbp": ("Annual contract value (GBP)", False, "CMDB.core_company"),
        "account_manager": ("Internal account manager", True, "CMDB.core_company"),
    },
    "incidents": {
        "incident_id": ("ITSM incident number", False, "ITSM export"),
        "opened_at": ("Timestamp the incident was logged (UTC, ISO-8601)", False, "ITSM export"),
        "resolved_at": ("Timestamp resolved; NULL if still open at snapshot", False, "ITSM export"),
        "status": ("ITSM state at snapshot", False, "ITSM export"),
        "priority": ("P1-P4. Imputed from impact x urgency matrix when missing", False, "ITSM export + rule"),
        "priority_imputed": ("1 if priority was imputed by the ETL", False, "derived"),
        "category": ("Service category (from CMDB service)", False, "derived"),
        "root_cause": ("Root cause code recorded at resolution", False, "ITSM export"),
        "short_description": ("Free-text summary. Untrusted user-supplied text", False, "ITSM export"),
        "caused_outage": ("1 if the incident caused customer-facing downtime", False, "ITSM export"),
        "outage_minutes": ("Customer-facing downtime in minutes", False, "ITSM export"),
        "resolution_hours": ("resolved_at - opened_at in hours", False, "derived"),
        "sla_target_hours": ("Resolution target for the priority", False, "derived from sla_policies"),
        "sla_breached": ("1 if resolution exceeded target (or open past target); NULL if open and within target", False, "derived"),
        "opened_month": ("YYYY-MM of opened_at", False, "derived"),
        "opened_quarter": ("YYYYQn of opened_at", False, "derived"),
    },
    "service_requests": {
        "request_id": ("ITSM requested-item number", False, "ITSM export"),
        "due_at": ("Committed delivery date", False, "ITSM export"),
        "blocked_reason": ("Why fulfilment is waiting, if anything", False, "ITSM export"),
        "fulfilment_days": ("closed_at - opened_at in days", False, "derived"),
        "met_due_date": ("1 if closed on/before due_at; NULL while open", False, "derived"),
    },
    "alerts": {
        "alert_id": ("Monitoring event id (deduplicated)", False, "Monitoring REST API"),
        "service_id": ("Service resolved via CMDB asset -> service", False, "derived"),
        "severity": ("Normalised to lower case", False, "Monitoring REST API"),
    },
    "costs": {
        "month": ("Accounting month YYYY-MM", False, "Finance export"),
        "cost_type": ("Staff, Licences, Third-party, Hardware or Energy", False, "Finance export"),
        "amount_gbp": ("Cost in GBP (parsed from currency string)", False, "Finance export"),
        "description": ("Finance ledger narrative", False, "Finance export"),
    },
}

# The single definition of each headline metric. KPI functions, the assistant and the
# evaluation ground truth all follow these, so "breach rate" means one thing.
METRIC_DEFINITIONS = {
    "sla_breach_rate": "Share of incidents opened in the period whose SLA outcome is known that breached the "
                       "resolution target. Open incidents count as breached once they pass target; open "
                       "incidents still inside target are excluded.",
    "mttr_hours": "Mean resolution_hours of incidents opened in the period and resolved.",
    "outage_minutes": "Sum of customer-facing downtime minutes of incidents opened in the period.",
    "operating_cost": "Sum of costs.amount_gbp for the accounting month(s).",
    "on_time_delivery_rate": "Share of closed service requests in the period that met their due date.",
}


def connect(path: Path | str | None = None, readonly: bool = False) -> sqlite3.Connection:
    path = Path(path or config.DB_PATH)
    if readonly:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    else:
        con = sqlite3.connect(path, check_same_thread=False)
        con.execute("PRAGMA foreign_keys = ON")
    con.row_factory = sqlite3.Row
    return con


@contextmanager
def session(path=None, readonly=False):
    con = connect(path, readonly)
    try:
        yield con
        if not readonly:
            con.commit()
    finally:
        con.close()


def init_schema(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    con.executemany(
        "INSERT OR REPLACE INTO catalog VALUES (?,?,?,?,?)",
        [(t, c, d, int(p), s) for t, cols in CATALOG.items() for c, (d, p, s) in cols.items()],
    )


def query_df(sql: str, params=(), con: sqlite3.Connection | None = None):
    import pandas as pd

    if con is not None:
        return pd.read_sql_query(sql, con, params=params)
    with session(readonly=True) as c:
        return pd.read_sql_query(sql, c, params=params)
