"""REST API for integration with other enterprise systems (ITSM, BI, chat ops).

    uvicorn opsintel.api.main:app --reload
Identity: demo header `X-User: <user_id>`. In a pilot this is replaced by an OIDC bearer
token whose group claims map onto the same roles.
"""
from __future__ import annotations

import json
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from opsintel import db
from opsintel.ai.assistant import ask
from opsintel.analytics import anomaly, kpis, risk
from opsintel.governance import actions, audit
from opsintel.governance.rbac import AccessDenied, User, get_user

app = FastAPI(title="OpsIntel AI", version="0.1.0",
              description="Governed operational-intelligence API: KPIs, risk, anomalies, AI decision support, actions and audit.")


def conn():
    con = db.connect()
    try:
        yield con
    finally:
        con.close()


def current_user(x_user: str = Header(..., description="Demo identity, e.g. opsmgr.demo"), con=Depends(conn)) -> User:
    try:
        return get_user(con, x_user)
    except AccessDenied as e:
        raise HTTPException(401, str(e))


def _need_costs(user: User):
    if "costs" not in user.role.tables:
        raise HTTPException(403, f"role {user.role.name} cannot view financial data")


def _bad(e: Exception):
    raise HTTPException(400, str(e))


@app.get("/health")
def health(con=Depends(conn)):
    run = con.execute("SELECT run_id, finished_at, status FROM etl_runs ORDER BY started_at DESC LIMIT 1").fetchone()
    return {"status": "ok", "last_etl_run": dict(run) if run else None, "coverage": kpis.data_coverage()}


@app.get("/kpis/headline")
def headline(user: User = Depends(current_user)):
    out = kpis.headline_kpis()
    if "costs" not in user.role.tables:
        out.pop("cost_gbp"), out.pop("cost_gbp_prev")
    return out


@app.get("/kpis/sla-breach-rate")
def sla(period: str = "last_quarter", group_by: Literal["category", "service", "priority", "business_unit", "assignment_group"] = "category",
        user: User = Depends(current_user)):
    try:
        return kpis.sla_breach_rate(period, group_by)
    except ValueError as e:
        _bad(e)


@app.get("/kpis/root-causes")
def root_causes(period: str = "last_quarter", category: str | None = None, rank_by: Literal["incidents", "outage_minutes", "breaches"] = "incidents",
                user: User = Depends(current_user)):
    try:
        return kpis.top_root_causes(period, category, None, rank_by)
    except ValueError as e:
        _bad(e)


@app.get("/kpis/downtime")
def downtime(months: int = Query(6, ge=1, le=18), user: User = Depends(current_user)):
    return kpis.downtime_causes(months)


@app.get("/kpis/cost-change")
def cost_change(month: str = "this_month", group_by: Literal["service_cost_type", "service", "cost_type", "business_unit"] = "service_cost_type",
                user: User = Depends(current_user)):
    _need_costs(user)
    try:
        return kpis.cost_change(month, group_by)
    except ValueError as e:
        _bad(e)


@app.get("/kpis/improvement-priorities")
def improvement(period: str = "last_quarter", user: User = Depends(current_user)):
    return kpis.improvement_priorities(period)


@app.get("/risk/sla-next-week")
def sla_risk(user: User = Depends(current_user)):
    return risk.sla_risk_next_week()


@app.get("/risk/delivery")
def delivery_risk(limit: int = Query(15, ge=1, le=100), user: User = Depends(current_user)):
    return risk.delivery_delay_risk(limit)


@app.get("/anomalies/{kind}")
def anomalies(kind: Literal["operational", "cost"], user: User = Depends(current_user)):
    if kind == "cost":
        _need_costs(user)
        return anomaly.cost_anomalies()
    return anomaly.operational_anomalies()


class AskBody(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    engine: Literal["auto", "claude", "rules"] = "auto"


@app.post("/ask")
def ask_endpoint(body: AskBody, user: User = Depends(current_user)):
    a = ask(body.question, user.user_id, engine=body.engine)
    return {"answer": a.answer, "engine": a.engine, "abstained": a.abstained, "grounding": a.grounding,
            "latency_ms": a.latency_ms, "injection_screened": len(a.injection_hits),
            "evidence": [{"id": e.evidence_id, "tool": e.tool, "args": e.args, "summary": e.summary, "sql": e.sql,
                          "sources": e.sources, "is_error": e.is_error} for e in a.evidence]}


class ProposeBody(BaseModel):
    title: str
    rationale: str
    evidence: list[dict] = Field(..., min_length=1)
    priority: Literal["P1", "P2", "P3", "P4"] = "P3"
    service_id: str | None = None
    owner_group: str | None = None


class DecisionBody(BaseModel):
    note: str = ""


class ProgressBody(BaseModel):
    status: Literal["in_progress", "done"]
    outcome: str = ""


def _act(fn, *a, **k):
    try:
        return fn(*a, **k)
    except AccessDenied as e:
        raise HTTPException(403, str(e))
    except KeyError as e:
        raise HTTPException(404, f"no action {e}")
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/actions")
def list_actions(status: str | None = None, user: User = Depends(current_user), con=Depends(conn)):
    return actions.list_actions(con, status)


@app.post("/actions", status_code=201)
def propose(body: ProposeBody, user: User = Depends(current_user), con=Depends(conn)):
    return _act(actions.propose, con, user, body.title, body.rationale, body.evidence, body.priority, body.service_id, body.owner_group)


@app.post("/actions/{action_id}/approve")
def approve(action_id: str, body: DecisionBody, user: User = Depends(current_user), con=Depends(conn)):
    return _act(actions.decide, con, user, action_id, True, body.note)


@app.post("/actions/{action_id}/reject")
def reject(action_id: str, body: DecisionBody, user: User = Depends(current_user), con=Depends(conn)):
    return _act(actions.decide, con, user, action_id, False, body.note)


@app.post("/actions/{action_id}/progress")
def progress(action_id: str, body: ProgressBody, user: User = Depends(current_user), con=Depends(conn)):
    return _act(actions.update_progress, con, user, action_id, body.status, body.outcome)


@app.get("/audit")
def audit_log(limit: int = Query(100, ge=1, le=1000), user: User = Depends(current_user), con=Depends(conn)):
    if not user.role.can_view_audit:
        raise HTTPException(403, "audit log is restricted to auditors and executives")
    rows = con.execute("SELECT * FROM audit_log ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) | {"detail": json.loads(r["detail"])} for r in rows]


@app.get("/audit/verify")
def audit_verify(user: User = Depends(current_user), con=Depends(conn)):
    if not user.role.can_view_audit:
        raise HTTPException(403, "audit log is restricted to auditors and executives")
    ok, bad = audit.verify(con)
    return {"chain_intact": ok, "first_bad_seq": bad}


@app.get("/data-quality")
def data_quality(user: User = Depends(current_user), con=Depends(conn)):
    run = con.execute("SELECT run_id FROM etl_runs WHERE status='succeeded' ORDER BY started_at DESC LIMIT 1").fetchone()
    if not run:
        raise HTTPException(404, "no ETL run")
    rows = con.execute("SELECT source, stage, metric, value FROM dq_results WHERE run_id=?", (run[0],)).fetchall()
    rejects = con.execute("SELECT source, reason, COUNT(*) n FROM etl_rejects WHERE run_id=? GROUP BY source, reason", (run[0],)).fetchall()
    return {"run_id": run[0], "metrics": [dict(r) for r in rows], "rejects": [dict(r) for r in rejects]}


@app.get("/lineage")
def lineage(user: User = Depends(current_user), con=Depends(conn)):
    rows = con.execute("SELECT l.* FROM lineage l JOIN etl_runs r USING (run_id) WHERE r.status='succeeded' "
                       "AND r.run_id = (SELECT run_id FROM etl_runs WHERE status='succeeded' ORDER BY started_at DESC LIMIT 1)").fetchall()
    return [dict(r) | {"transforms": json.loads(r["transforms"])} for r in rows]


@app.get("/catalog")
def catalog(user: User = Depends(current_user), con=Depends(conn)):
    return {"metric_definitions": db.METRIC_DEFINITIONS,
            "columns": [dict(r) for r in con.execute("SELECT * FROM catalog ORDER BY table_name, column_name")]}
