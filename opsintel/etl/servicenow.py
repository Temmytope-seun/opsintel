"""ServiceNow source: extract a real instance through the Table API into the same raw
landing format the pipeline already consumes (CMDB database + ITSM CSV exports).

    python -m opsintel.cli servicenow-test        # check connectivity and read access
    python -m opsintel.cli servicenow-sync        # extract -> data_servicenow/ -> ETL

Credentials come only from the environment (or a git-ignored `.env` file you create):
    SN_INSTANCE        e.g. https://dev12345.service-now.com
    and either OAuth 2.0 client credentials (preferred; required where basic auth is blocked)
    SN_CLIENT_ID / SN_CLIENT_SECRET
    or basic auth for a read-only integration user
    SN_USERNAME / SN_PASSWORD

Design notes
* Read-only: data is only ever read with HTTP GET (the one POST is the OAuth token request).
* Landing, not loading: data is written in the same raw shapes as the synthetic
  sources, so the *same* validation, entity matching, quarantine and lineage run on it.
* Mapping gaps are explicit and recorded in the manifest rather than invented:
  outages are not modelled in a standard instance (outage minutes = 0); SLA targets use
  the P1-P4 policy table; requests without a due date get a configurable default target.
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from opsintel import config

PAGE_SIZE = 1000
UNASSIGNED_SERVICE = ("SN-UNASSIGNED", "Unassigned service")
INTERNAL_CUSTOMER = ("SN-INTERNAL", "Internal / unspecified")
UNASSIGNED_BU = ("BU-UNASSIGNED", "Unassigned business unit")
DEFAULT_REQUEST_TARGET_DAYS = float(os.environ.get("OPSINTEL_SN_DEFAULT_TARGET_DAYS", "5"))
# ServiceNow priority 1-5 -> platform priority (5 "Planning" folds into P4).
PRIORITY = {"1": "P1", "2": "P2", "3": "P3", "4": "P4", "5": "P4"}
SLA_POLICIES = [("P1", "Critical", 0.25, 4), ("P2", "High", 1, 8), ("P3", "Moderate", 4, 24), ("P4", "Low", 8, 72)]


class ServiceNowError(RuntimeError):
    pass


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env reader (KEY=VALUE lines). Existing environment variables win."""
    path = path or (config.ROOT / ".env")
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass
class Credentials:
    """Basic auth (SN_USERNAME + SN_PASSWORD) or OAuth 2.0 client credentials
    (SN_CLIENT_ID + SN_CLIENT_SECRET). OAuth is used when a client id is set."""
    instance: str
    username: str = ""
    password: str = field(default="", repr=False)
    client_id: str = ""
    client_secret: str = field(default="", repr=False)

    @property
    def mode(self) -> str:
        return "oauth" if self.client_id else "basic"

    @property
    def principal(self) -> str:
        return f"OAuth client {self.client_id[:8]}…" if self.client_id else self.username

    @classmethod
    def from_env(cls) -> "Credentials":
        load_dotenv()
        env = os.environ.get
        if env("SN_CLIENT_ID"):
            need = ("SN_INSTANCE", "SN_CLIENT_ID", "SN_CLIENT_SECRET")
        else:
            need = ("SN_INSTANCE", "SN_USERNAME", "SN_PASSWORD")
        missing = [k for k in need if not env(k)]
        if missing:
            raise ServiceNowError(f"Missing environment variables: {', '.join(missing)}. See .env.example.")
        inst = env("SN_INSTANCE").strip().rstrip("/")
        if not inst.startswith("http"):
            inst = f"https://{inst}"
        if not inst.startswith("https://"):
            raise ServiceNowError("SN_INSTANCE must use https://")
        return cls(inst, env("SN_USERNAME", ""), env("SN_PASSWORD", ""), env("SN_CLIENT_ID", ""), env("SN_CLIENT_SECRET", ""))


class ServiceNowClient:
    def __init__(self, creds: Credentials, transport: httpx.BaseTransport | None = None, timeout: float = 60):
        self.creds = creds
        auth = (creds.username, creds.password) if creds.mode == "basic" else None
        self.http = httpx.Client(base_url=creds.instance, auth=auth, timeout=timeout,
                                 headers={"Accept": "application/json"}, transport=transport)
        self.requests_made = 0
        self._token_expiry = 0.0
        if creds.mode == "oauth":
            self._refresh_token()

    def _refresh_token(self) -> None:
        """OAuth 2.0 client-credentials grant against the instance's token endpoint."""
        r = self.http.post("/oauth_token.do", data={"grant_type": "client_credentials", "client_id": self.creds.client_id,
                                                     "client_secret": self.creds.client_secret})
        self.requests_made += 1
        if r.status_code != 200 or "access_token" not in r.text:
            detail = ""
            try:
                detail = r.json().get("error_description") or r.json().get("error") or ""
            except ValueError:
                pass
            raise ServiceNowError(f"OAuth token request failed ({r.status_code}) {detail}".strip()
                                  + " - check SN_CLIENT_ID / SN_CLIENT_SECRET and that the client-credentials grant is enabled.")
        body = r.json()
        self.http.headers["Authorization"] = f"Bearer {body['access_token']}"
        self._token_expiry = time.time() + float(body.get("expires_in", 1800)) - 60

    def close(self):
        self.http.close()

    def _get(self, path: str, params: dict) -> httpx.Response:
        for attempt in range(5):
            if self.creds.mode == "oauth" and time.time() > self._token_expiry:
                self._refresh_token()
            r = self.http.get(path, params=params)
            self.requests_made += 1
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(min(30, float(r.headers.get("Retry-After", 2 ** attempt))))
                continue
            if r.status_code == 401:
                hint = "SN_CLIENT_ID / SN_CLIENT_SECRET" if self.creds.mode == "oauth" else "SN_USERNAME / SN_PASSWORD"
                raise ServiceNowError(f"Authentication failed (401): check {hint}.")
            if r.status_code == 403:
                raise ServiceNowError(f"Access denied (403) reading {path}: the user needs read roles for this table.")
            if r.status_code == 404:
                raise ServiceNowError(f"Not found (404): {path} - table may not exist on this instance.")
            r.raise_for_status()
            return r
        raise ServiceNowError(f"Gave up on {path} after repeated 429/5xx responses.")

    def table(self, table: str, fields: list[str], query: str = "", limit: int | None = None) -> list[dict]:
        """All rows of a table (paged). Returns raw values; reference fields as {'value','display_value'}."""
        rows, offset = [], 0
        while True:
            params = {"sysparm_fields": ",".join(fields), "sysparm_limit": PAGE_SIZE, "sysparm_offset": offset,
                      "sysparm_display_value": "all", "sysparm_exclude_reference_link": "true",
                      "sysparm_query": (query + "^" if query else "") + "ORDERBYsys_created_on"}
            batch = self._get(f"/api/now/table/{table}", params).json().get("result", [])
            rows.extend(batch)
            if len(batch) < PAGE_SIZE or (limit and len(rows) >= limit):
                return rows[:limit] if limit else rows
            offset += PAGE_SIZE


# --------------------------------------------------------------------------- field helpers

def v(row: dict, f: str) -> str:
    """Raw (stored) value of a field returned with sysparm_display_value=all."""
    x = row.get(f, "")
    return (x.get("value") or "") if isinstance(x, dict) else (x or "")


def d(row: dict, f: str) -> str:
    """Display value of a field."""
    x = row.get(f, "")
    return (x.get("display_value") or "") if isinstance(x, dict) else (x or "")


# --------------------------------------------------------------------------- extraction

INCIDENT_FIELDS = ["sys_id", "number", "opened_at", "resolved_at", "closed_at", "state", "priority", "impact", "urgency",
                   "business_service", "company", "cmdb_ci", "category", "subcategory", "problem_id", "assignment_group", "close_code",
                   "short_description", "reopen_count", "sys_updated_on"]
REQUEST_FIELDS = ["sys_id", "number", "opened_at", "closed_at", "due_date", "estimated_delivery", "state", "cat_item",
                  "assignment_group", "company", "sys_updated_on"]


def check_access(client: ServiceNowClient) -> dict:
    """Read one row from each table the sync needs; report what is readable."""
    out = {}
    for t in ("incident", "sc_req_item", "cmdb_ci_service", "cmdb_ci", "core_company", "business_unit"):
        try:
            client.table(t, ["sys_id"], limit=1)
            out[t] = "ok"
        except ServiceNowError as e:
            out[t] = str(e)
            if "401" in str(e):
                # Stop at the first failed login: repeated failures lock the account.
                out["_stopped"] = "stopped after the first authentication failure to avoid locking the account"
                break
    return out


def extract(client: ServiceNowClient, since_days: int | None = None) -> dict:
    q = ""
    if since_days:
        q = f"opened_at>=javascript:gs.daysAgoStart({int(since_days)})"
    incidents = client.table("incident", INCIDENT_FIELDS, q)
    requests = client.table("sc_req_item", REQUEST_FIELDS, q)
    services = client.table("cmdb_ci_service", ["sys_id", "name", "service_classification", "busines_criticality",
                                                 "support_group", "department"])
    companies = client.table("core_company", ["sys_id", "name", "customer", "industry"])
    try:
        bus = client.table("business_unit", ["sys_id", "name"])
    except ServiceNowError:
        bus = []
    ci_ids = sorted({v(r, "cmdb_ci") for r in incidents if v(r, "cmdb_ci")})
    cis = []
    for i in range(0, len(ci_ids), 100):  # fetch only CIs that incidents reference
        cis += client.table("cmdb_ci", ["sys_id", "name", "sys_class_name", "manufacturer", "install_date",
                                        "operational_status", "location"], "sys_idIN" + ",".join(ci_ids[i:i + 100]))
    return {"incidents": incidents, "requests": requests, "services": services, "companies": companies,
            "business_units": bus, "cis": cis, "requests_made": client.requests_made}


# --------------------------------------------------------------------------- landing (raw format)

def _ts(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S") if s else None
    except ValueError:
        return None


def land(raw: dict, out_dir: Path, instance: str) -> dict:
    """Write the extract in the platform's raw landing format. Returns the manifest."""
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    gaps = {"incidents_without_service": 0, "incidents_without_company": 0, "incidents_without_close_code": 0,
            "requests_default_due_date": 0, "cis_without_service": 0}

    bus = [(v(r, "sys_id"), d(r, "name") or v(r, "name")) for r in raw["business_units"]]
    bus = [b for b in bus if b[0]] + [UNASSIGNED_BU]
    bu_ids = {b[0] for b in bus}

    services = []
    for r in raw["services"]:
        dep = v(r, "department")
        services.append({"service_id": v(r, "sys_id"), "name": d(r, "name"), "category": d(r, "service_classification") or "Business Service",
                         "bu_id": dep if dep in bu_ids else UNASSIGNED_BU[0], "tier": d(r, "busines_criticality") or "Unspecified",
                         "owner_group": d(r, "support_group") or "Unassigned", "aliases": ""})
    services.append({"service_id": UNASSIGNED_SERVICE[0], "name": UNASSIGNED_SERVICE[1], "category": "Unassigned",
                     "bu_id": UNASSIGNED_BU[0], "tier": "Unspecified", "owner_group": "Unassigned", "aliases": ""})
    svc_by_sysid = {s["service_id"]: s for s in services}

    customers = [{"customer_id": v(r, "sys_id"), "name": d(r, "name"), "sector": d(r, "industry") or None,
                  "contact_email": None, "contact_phone": None, "contract_value_gbp": None, "account_manager": None}
                 for r in raw["companies"]]
    customers.append({"customer_id": INTERNAL_CUSTOMER[0], "name": INTERNAL_CUSTOMER[1], "sector": None, "contact_email": None,
                      "contact_phone": None, "contract_value_gbp": None, "account_manager": None})
    cust_ids = {c["customer_id"] for c in customers}

    # Asset -> service: the business service most often recorded on that CI's incidents.
    ci_service: dict[str, dict] = {}
    for r in raw["incidents"]:
        ci, svc = v(r, "cmdb_ci"), v(r, "business_service")
        if ci and svc in svc_by_sysid:
            ci_service.setdefault(ci, {}).setdefault(svc, 0)
            ci_service[ci][svc] += 1
    assets = []
    for r in raw["cis"]:
        sid = v(r, "sys_id")
        counts = ci_service.get(sid)
        service = max(counts, key=counts.get) if counts else UNASSIGNED_SERVICE[0]
        gaps["cis_without_service"] += 0 if counts else 1
        assets.append({"asset_id": sid, "service_id": service, "asset_type": d(r, "sys_class_name") or "Configuration item",
                       "vendor": d(r, "manufacturer") or None, "install_date": v(r, "install_date") or None,
                       "status": d(r, "operational_status") or None, "location": d(r, "location") or None, "firmware_version": None})
    asset_ids = {a["asset_id"] for a in assets}

    cmdb = raw_dir / "cmdb.sqlite"
    if cmdb.exists():
        cmdb.unlink()
    with sqlite3.connect(cmdb) as con:
        con.execute("CREATE TABLE cmdb_business_unit (bu_id TEXT, name TEXT)")
        con.executemany("INSERT INTO cmdb_business_unit VALUES (?,?)", bus)
        con.execute("CREATE TABLE cmdb_service (service_id TEXT, name TEXT, category TEXT, bu_id TEXT, tier TEXT, owner_group TEXT, aliases TEXT)")
        con.executemany("INSERT INTO cmdb_service VALUES (:service_id,:name,:category,:bu_id,:tier,:owner_group,:aliases)", services)
        con.execute("CREATE TABLE sla_definition (priority TEXT, label TEXT, response_target_hrs REAL, resolution_target_hrs REAL)")
        con.executemany("INSERT INTO sla_definition VALUES (?,?,?,?)", SLA_POLICIES)
        con.execute("CREATE TABLE core_company (customer_id TEXT, name TEXT, sector TEXT, contact_email TEXT, contact_phone TEXT, "
                    "contract_value_gbp INTEGER, account_manager TEXT)")
        con.executemany("INSERT INTO core_company VALUES (:customer_id,:name,:sector,:contact_email,:contact_phone,:contract_value_gbp,:account_manager)", customers)
        con.execute("CREATE TABLE cmdb_ci (asset_id TEXT, service_id TEXT, asset_type TEXT, vendor TEXT, install_date TEXT, status TEXT, "
                    "location TEXT, firmware_version TEXT)")
        con.executemany("INSERT INTO cmdb_ci VALUES (:asset_id,:service_id,:asset_type,:vendor,:install_date,:status,:location,:firmware_version)", assets)

    inc_cols = ["incident_id", "opened_at", "resolved_at", "service", "customer_id", "asset_id", "impact", "urgency", "priority",
                "category", "assignment_group", "root_cause", "short_description", "caused_outage", "outage_minutes", "reopened",
                "status", "sys_updated_on"]
    dates = []
    with open(raw_dir / "itsm_incidents.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=inc_cols)
        w.writeheader()
        for r in raw["incidents"]:
            svc = v(r, "business_service")
            name = svc_by_sysid[svc]["name"] if svc in svc_by_sysid else UNASSIGNED_SERVICE[1]
            gaps["incidents_without_service"] += 0 if svc in svc_by_sysid else 1
            comp = v(r, "company")
            if comp not in cust_ids:
                gaps["incidents_without_company"] += 1
                comp = INTERNAL_CUSTOMER[0]
            close = d(r, "close_code")
            # Root cause: the linked problem says *why*; subcategory is the next-best signal;
            # the close code (how the ticket was closed) is the last resort.
            cause = d(r, "problem_id") or (f"{d(r, 'category')} / {d(r, 'subcategory')}" if d(r, "subcategory") else "")
            gaps["incidents_without_close_code"] += 0 if close or not v(r, "resolved_at") else 1
            resolved = v(r, "resolved_at") or v(r, "closed_at")
            if _ts(v(r, "opened_at")):
                dates.append(_ts(v(r, "opened_at")))
            w.writerow({"incident_id": v(r, "number"), "opened_at": v(r, "opened_at"), "resolved_at": resolved,
                        "service": name, "customer_id": comp, "asset_id": v(r, "cmdb_ci") if v(r, "cmdb_ci") in asset_ids else "",
                        "impact": v(r, "impact") or "3", "urgency": v(r, "urgency") or "3", "priority": PRIORITY.get(v(r, "priority"), ""),
                        "category": d(r, "category") or "Uncategorised", "assignment_group": d(r, "assignment_group") or "Unassigned",
                        "root_cause": cause or close or ("Not recorded" if resolved else ""), "short_description": d(r, "short_description"),
                        "caused_outage": "False", "outage_minutes": "0", "reopened": str(int(v(r, "reopen_count") or 0) > 0),
                        "status": d(r, "state") or "Unknown", "sys_updated_on": v(r, "sys_updated_on")})

    req_cols = ["request_id", "opened_at", "due_at", "closed_at", "service", "customer_id", "request_type", "target_days",
                "blocked_reason", "assignment_group", "status"]
    with open(raw_dir / "itsm_requests.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=req_cols)
        w.writeheader()
        for r in raw["requests"]:
            opened = _ts(v(r, "opened_at"))
            if not opened:
                continue
            due = _ts(v(r, "due_date")) or _ts(v(r, "estimated_delivery"))
            if not due or due <= opened:
                gaps["requests_default_due_date"] += 1
                due = opened + timedelta(days=DEFAULT_REQUEST_TARGET_DAYS)
            dates.append(opened)
            comp = v(r, "company")
            w.writerow({"request_id": v(r, "number"), "opened_at": v(r, "opened_at"), "due_at": due.strftime("%Y-%m-%d %H:%M:%S"),
                        "closed_at": v(r, "closed_at"), "service": UNASSIGNED_SERVICE[1],
                        "customer_id": comp if comp in cust_ids else INTERNAL_CUSTOMER[0],
                        "request_type": d(r, "cat_item") or "Uncatalogued request",
                        "target_days": round((due - opened).total_seconds() / 86400, 3), "blocked_reason": "",
                        "assignment_group": d(r, "assignment_group") or "Unassigned", "status": d(r, "state") or "Unknown"})

    manifest = {
        "source": "servicenow", "instance": instance, "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": {"incidents": len(raw["incidents"]), "requests": len(raw["requests"]), "services": len(raw["services"]),
                 "companies": len(raw["companies"]), "business_units": len(raw["business_units"]), "cis": len(raw["cis"])},
        "api_requests": raw.get("requests_made"),
        "data_start": min(dates).date().isoformat() if dates else None,
        "snapshot_date": max(dates).date().isoformat() if dates else None,
        "mapping_gaps": gaps,
        "not_available_from_standard_instance": ["finance ledger (costs)", "monitoring alerts", "outage minutes"],
    }
    (out_dir / "source_manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
