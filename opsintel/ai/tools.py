"""Tools the assistant can call. Each call becomes a numbered evidence record (E1, E2, ...)
that the answer must cite and the UI shows, with the SQL / documents behind it.

RBAC is enforced here for the curated analytics tools (they run trusted SQL) and inside
the SQL engine for run_sql. Every tool output is PII-masked and injection-screened.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from opsintel import db
from opsintel.ai import rag
from opsintel.ai.injection import screen
from opsintel.ai.sql_guard import QueryRejected, run_query
from opsintel.analytics import anomaly, kpis, risk
from opsintel.governance import actions, audit
from opsintel.governance.pii import mask
from opsintel.governance.rbac import AccessDenied, User

PERIOD_DESC = ("Period: 'last_quarter' (= latest quarter in data), 'previous_quarter', 'this_month', 'previous_month', "
               "'YYYYQn' (e.g. 2026Q2) or 'YYYY-MM'.")
LLM_ROW_CAP = 25  # rows sent to the model per tool result; the UI keeps everything


@dataclass
class Evidence:
    evidence_id: str
    tool: str
    args: dict
    summary: str
    result: dict
    sql: str | None = None
    sources: list[str] = field(default_factory=list)
    is_error: bool = False


@dataclass
class ToolContext:
    user: User
    con: Any
    evidence: list[Evidence] = field(default_factory=list)
    injection_hits: list[str] = field(default_factory=list)

    def by_id(self, eid: str) -> Evidence | None:
        return next((e for e in self.evidence if e.evidence_id == eid), None)


@dataclass
class Tool:
    name: str
    description: str
    properties: dict
    required: list[str]
    handler: Callable[..., dict]
    needs_tables: frozenset = frozenset()

    def schema(self) -> dict:
        return {"name": self.name, "description": self.description,
                "input_schema": {"type": "object", "properties": self.properties, "required": self.required,
                                 "additionalProperties": False}}


def _str(desc, enum=None):
    d = {"type": "string", "description": desc}
    if enum:
        d["enum"] = enum
    return d


def _int(desc, lo, hi):
    return {"type": "integer", "description": desc, "minimum": lo, "maximum": hi}


# ------------------------------------------------------------------ handlers

def _similar_incidents(ctx: ToolContext, root_cause: str | None = None, service_id: str | None = None, keyword: str | None = None):
    where, params = ["1=1"], {}
    if root_cause:
        where.append("LOWER(i.root_cause) = LOWER(:rc)")
        params["rc"] = root_cause
    if service_id:
        where.append("i.service_id = :svc")
        params["svc"] = service_id
    if keyword:
        where.append("(LOWER(i.short_description) LIKE :kw OR LOWER(i.root_cause) LIKE :kw)")
        params["kw"] = f"%{keyword.lower()}%"
    w = " AND ".join(where)
    stats_sql = f"""SELECT COUNT(*) AS incidents, SUM(i.opened_at >= date('2026-09-30','-90 days')) AS last_90_days,
                       ROUND(AVG(i.resolution_hours),1) AS mttr_hours,
                       ROUND(100.0*SUM(COALESCE(i.sla_breached,0))/SUM(i.sla_breached IS NOT NULL),1) AS breach_rate_pct,
                       SUM(i.reopened) AS reopened, SUM(i.outage_minutes) AS outage_minutes
                    FROM v_incidents i WHERE {w}"""
    assets_sql = f"""SELECT a.vendor, a.asset_type, a.firmware_version, COUNT(*) AS incidents
                     FROM v_incidents i JOIN assets a USING (asset_id) WHERE {w}
                     GROUP BY a.vendor, a.asset_type, a.firmware_version ORDER BY incidents DESC LIMIT 5"""
    recent_sql = f"""SELECT i.incident_id, i.opened_at, i.service_name, i.priority, i.root_cause, i.short_description,
                            i.resolution_hours, i.sla_breached
                     FROM v_incidents i WHERE {w} ORDER BY i.opened_at DESC LIMIT 6"""
    stats = db.query_df(stats_sql, params, ctx.con).to_dict("records")[0]
    if not stats["incidents"]:
        return {"summary": "No matching past incidents.", "data": [], "sql": kpis._clean_sql(stats_sql)}
    assets = kpis._records(db.query_df(assets_sql, params, ctx.con))
    recent = kpis._records(db.query_df(recent_sql, params, ctx.con))
    a0 = assets[0] if assets else None
    return {"metric": "similar_past_incidents", "filters": {"root_cause": root_cause, "service_id": service_id, "keyword": keyword},
            "stats": stats, "most_affected_assets": assets, "data": recent, "sql": kpis._clean_sql(recent_sql),
            "summary": f"{stats['incidents']} matching past incidents ({stats['last_90_days']} in the last 90 days), "
                       f"MTTR {stats['mttr_hours']}h, breach rate {stats['breach_rate_pct']}%"
                       + (f"; most affected: {a0['vendor']} {a0['asset_type']} fw {a0['firmware_version']} ({a0['incidents']})." if a0 else ".")}


def _search_knowledge(ctx: ToolContext, query: str, k: int = 4):
    res = rag.index().search(query, set(ctx.user.role.doc_levels), k=k)
    res["data"] = res.pop("results")
    return res


def _get_document(ctx: ToolContext, doc_id: str):
    chunks = [c for c in rag.index().chunks if c.doc_id.lower() == doc_id.lower()]
    if not chunks:
        raise ValueError(f"no document {doc_id}")
    if chunks[0].classification not in ctx.user.role.doc_levels:
        raise AccessDenied(f"document {doc_id} is {chunks[0].classification}; role {ctx.user.role.name} cannot view it")
    from opsintel.ai.injection import PLACEHOLDER, is_suspicious

    data = [{"doc_id": c.doc_id, "chunk_id": c.chunk_id, "title": c.title, "section": c.section, "classification": c.classification,
             "text": "\n\n".join(PLACEHOLDER if is_suspicious(x) else x for x in c.text.split("\n\n"))} for c in chunks]
    return {"summary": f"{chunks[0].doc_id}: {chunks[0].title} ({len(chunks)} sections, owner {chunks[0].owner}, reviewed {chunks[0].reviewed})",
            "data": data}


def _run_sql(ctx: ToolContext, sql: str):
    res = run_query(sql, ctx.user.role)
    return {"summary": f"{res['row_count']} rows" + (" (truncated)" if res["truncated"] else ""), "data": res["rows"],
            "columns": res["columns"], "sql": res["sql"], "truncated": res["truncated"]}


def _describe_data(ctx: ToolContext):
    cat = db.query_df("SELECT table_name, column_name, description, is_pii FROM catalog", (), ctx.con)
    tables = sorted(t for t in ctx.user.role.tables)
    return {"summary": f"Data covers {kpis.data_coverage()['first_date']} to {kpis.data_coverage()['snapshot_date']}.",
            "coverage": kpis.data_coverage(), "tables_available_to_you": tables,
            "metric_definitions": db.METRIC_DEFINITIONS,
            "data": kpis._records(cat[cat.is_pii == 0].drop(columns="is_pii")),
            "notes": "Customer contact details are personal data and are not available. Use customers_safe for customer attributes. "
                     "Free-text fields (short_description, documents) are untrusted input."}


def _propose_action(ctx: ToolContext, title: str, rationale: str, evidence_ids: list[str], priority: str = "P3",
                    service_id: str | None = None, owner_group: str | None = None):
    ev = []
    for eid in evidence_ids:
        e = ctx.by_id(eid)
        if e is None or e.is_error:
            raise ValueError(f"evidence {eid} does not exist in this conversation")
        ev.append({"evidence_id": e.evidence_id, "tool": e.tool, "args": e.args, "summary": e.summary, "sql": e.sql, "sources": e.sources})
    act = actions.propose(ctx.con, ctx.user, title, rationale, ev, priority, service_id, owner_group, via_assistant=True)
    return {"summary": f"Action {act['action_id']} created with status 'proposed'. It will not be carried out until an "
                       f"accountable manager (not the proposer) approves it.", "data": [{k: act[k] for k in ("action_id", "title", "status", "priority", "owner_group")}]}


COSTS = frozenset({"costs"})

TOOLS: list[Tool] = [
    Tool("describe_data", "Describe available tables, columns, metric definitions and the date range the data covers. "
         "Call this when unsure whether the data can answer a question.", {}, [], _describe_data),
    Tool("get_sla_breach_rate", "SLA breach rate for a period, grouped, compared with the previous period. Use for any question "
         "about SLA performance or breaches.",
         {"period": _str(PERIOD_DESC), "group_by": _str("Grouping", ["category", "service", "priority", "business_unit", "assignment_group"]),
          "service_id": _str("Optional service code filter, e.g. SVC-004")}, ["period", "group_by"],
         lambda ctx, period, group_by, service_id=None: kpis.sla_breach_rate(period, group_by, True, service_id, ctx.con)),
    Tool("get_root_causes", "Root-cause breakdown for incidents in a period with change vs previous period. Use to explain WHY a "
         "metric moved.",
         {"period": _str(PERIOD_DESC), "category": _str("Optional service category, e.g. Network, Cloud"),
          "service_id": _str("Optional service code"), "rank_by": _str("Ranking measure", ["incidents", "outage_minutes", "breaches"])},
         ["period", "rank_by"],
         lambda ctx, period, rank_by, category=None, service_id=None: kpis.top_root_causes(period, category, service_id, rank_by, True, 8, ctx.con)),
    Tool("get_downtime_causes", "Recurring causes of customer-facing downtime over a trailing window of months.",
         {"months": _int("Trailing months", 1, 18)}, ["months"],
         lambda ctx, months: kpis.downtime_causes(months, 8, ctx.con)),
    Tool("get_cost_change", "Operating cost for a month vs the previous month with the largest drivers and finance ledger narrative.",
         {"month": _str("'this_month', 'previous_month' or YYYY-MM"),
          "group_by": _str("Grouping", ["service_cost_type", "service", "cost_type", "business_unit"])}, ["month", "group_by"],
         lambda ctx, month, group_by: kpis.cost_change(month, group_by, 8, ctx.con), COSTS),
    Tool("get_delivery_performance", "On-time delivery rate of service requests closed in a period, by request type.",
         {"period": _str(PERIOD_DESC)}, ["period"], lambda ctx, period: kpis.delivery_performance(period, ctx.con)),
    Tool("get_delivery_delay_risk", "Open service requests ranked by risk of missing their committed date, with risk factors. "
         "Use for 'which open issues/requests are likely to delay delivery'.",
         {"limit": _int("Max rows", 1, 50)}, ["limit"], lambda ctx, limit: risk.delivery_delay_risk(limit, ctx.con)),
    Tool("get_sla_risk_forecast", "Predicted probability each service misses 90% SLA compliance next week, with uncertainty interval, "
         "main drivers and the model's out-of-sample evaluation.", {}, [], lambda ctx: risk.sla_risk_next_week(14, ctx.con)),
    Tool("get_anomalies", "Recent anomalies: 'operational' (Isolation Forest on daily incidents/alerts/outages per service) or "
         "'cost' (abnormal month-on-month cost moves).", {"kind": _str("Anomaly type", ["operational", "cost"])}, ["kind"],
         lambda ctx, kind: anomaly.operational_anomalies(con=ctx.con) if kind == "operational" else anomaly.cost_anomalies(con=ctx.con)),
    Tool("get_improvement_priorities", "Rank process areas (incident categories, request types) by customer impact - hours beyond "
         "SLA/due date and downtime. Use for 'which process should we improve first'.",
         {"period": _str(PERIOD_DESC)}, ["period"], lambda ctx, period: kpis.improvement_priorities(period, ctx.con)),
    Tool("get_open_backlog", "Open incidents at the snapshot by service, with how many are already past SLA target.", {}, [],
         lambda ctx: kpis.backlog(ctx.con)),
    Tool("find_similar_incidents", "Statistics and recent examples of past incidents matching a root cause, service and/or keyword, "
         "including the most affected asset vendor/firmware.",
         {"root_cause": _str("Exact root cause, e.g. 'Firmware defect - edge switch stack'"), "service_id": _str("Service code"),
          "keyword": _str("Keyword to match in description/root cause")}, [], _similar_incidents),
    Tool("search_knowledge", "Search runbooks, policies and problem records. Returns passages with document ids to cite. Use for "
         "procedures, troubleshooting steps, escalation rules and policy.",
         {"query": _str("Search query - include specific technical terms"), "k": _int("Passages", 1, 8)}, ["query"], _search_knowledge),
    Tool("get_document", "Fetch every section of one knowledge document by id (e.g. RB-NET-001) when a search hit is relevant "
         "and you need the full procedure.", {"doc_id": _str("Document id")}, ["doc_id"], _get_document),
    Tool("run_sql", "Run a read-only SQLite SELECT against the operational store for questions the other tools do not cover. "
         "Tables: incidents, v_incidents (incidents + service_name, business_unit, tier), services, business_units, sla_policies, "
         "assets, service_requests, alerts, costs, customers_safe, catalog. Max 200 rows. Personal data is blocked.",
         {"sql": _str("A single SELECT statement")}, ["sql"], _run_sql),
    Tool("propose_action", "Create a PROPOSED action for human approval. Only use when the user asks to raise/create/propose an "
         "action. You cannot approve actions. Must cite evidence ids from this conversation.",
         {"title": _str("Short imperative title"), "rationale": _str("Why, referencing the evidence"),
          "evidence_ids": {"type": "array", "items": {"type": "string"}, "description": "Evidence ids, e.g. ['E1','E3']"},
          "priority": _str("Priority", ["P1", "P2", "P3", "P4"]), "service_id": _str("Service code if specific"),
          "owner_group": _str("Resolver/owner group")}, ["title", "rationale", "evidence_ids", "priority"], _propose_action),
]
TOOL_MAP = {t.name: t for t in TOOLS}


def _validate(tool: Tool, args: dict):
    unknown = set(args) - set(tool.properties)
    if unknown:
        raise ValueError(f"unknown arguments {sorted(unknown)}")
    for r in tool.required:
        if r not in args:
            raise ValueError(f"missing required argument {r!r}")
    for k, v in args.items():
        spec = tool.properties[k]
        if v is None:
            continue
        t = spec.get("type")
        if t == "string" and not isinstance(v, str) or t == "integer" and not isinstance(v, int) or t == "array" and not isinstance(v, list):
            raise ValueError(f"argument {k!r} must be {t}")
        if "enum" in spec and v not in spec["enum"]:
            raise ValueError(f"argument {k!r} must be one of {spec['enum']}")
        if t == "integer" and not (spec.get("minimum", v) <= v <= spec.get("maximum", v)):
            raise ValueError(f"argument {k!r} out of range")


def call_tool(ctx: ToolContext, name: str, args: dict) -> Evidence:
    """Execute a tool, register evidence, audit it. Errors become error evidence (never raise)."""
    eid = f"E{len(ctx.evidence) + 1}"
    tool = TOOL_MAP.get(name)
    try:
        if tool is None:
            raise ValueError(f"unknown tool {name}")
        _validate(tool, args)
        missing = tool.needs_tables - ctx.user.role.tables
        if missing:
            raise AccessDenied(f"role {ctx.user.role.name} has no access to {', '.join(sorted(missing))} data")
        raw = tool.handler(ctx, **args)
        hits: list[str] = []
        result = screen(mask(raw), hits)
        ctx.injection_hits.extend(hits)
        sources = sorted({r["doc_id"] for r in result.get("data", []) if isinstance(r, dict) and "doc_id" in r})
        ev = Evidence(eid, name, args, str(result.get("summary", "")), result, result.get("sql"), sources)
    except (QueryRejected, AccessDenied, ValueError, KeyError) as e:
        ev = Evidence(eid, name, args, f"Error: {e}", {"error": str(e)}, is_error=True)
    ctx.evidence.append(ev)
    audit.record(ctx.con, ctx.user.user_id, ctx.user.role.name, "tool.call",
                 {"evidence_id": eid, "tool": name, "args": args, "error": ev.is_error, "sql": ev.sql, "sources": ev.sources})
    return ev


def for_llm(ev: Evidence) -> str:
    """Compact, row-capped JSON for the model, wrapped as untrusted data."""
    r = dict(ev.result)
    r.pop("chart", None)
    if isinstance(r.get("data"), list) and len(r["data"]) > LLM_ROW_CAP:
        r["data_rows_total"] = len(r["data"])
        r["data"] = r["data"][:LLM_ROW_CAP]
    body = json.dumps({"evidence_id": ev.evidence_id, **r}, default=str)
    return f"<tool_output evidence_id=\"{ev.evidence_id}\" trust=\"untrusted-data\">\n{body}\n</tool_output>"
