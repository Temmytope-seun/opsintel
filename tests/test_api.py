from fastapi.testclient import TestClient

from opsintel.api.main import app

c = TestClient(app)
H = lambda u: {"X-User": u}  # noqa: E731


def test_health_and_identity():
    assert c.get("/health").json()["status"] == "ok"
    assert c.get("/kpis/headline").status_code == 422                 # header required
    assert c.get("/kpis/headline", headers=H("nobody")).status_code == 401


def test_rbac_on_financials_and_audit():
    assert c.get("/kpis/cost-change", headers=H("desk.demo")).status_code == 403
    assert c.get("/kpis/cost-change", headers=H("exec.demo")).status_code == 200
    assert "cost_gbp" not in c.get("/kpis/headline", headers=H("desk.demo")).json()
    assert c.get("/audit", headers=H("analyst.demo")).status_code == 403
    assert c.get("/audit/verify", headers=H("audit.demo")).json()["chain_intact"] is True


def test_ask_and_action_flow():
    r = c.post("/ask", headers=H("analyst.demo"), json={"question": "What are the recurring causes of service downtime?", "engine": "rules"}).json()
    assert r["evidence"] and r["grounding"]["ungrounded"] == []
    act = c.post("/actions", headers=H("analyst.demo"), json={"title": "Fix firmware", "rationale": "downtime",
                                                              "evidence": [r["evidence"][0]], "priority": "P2"}).json()
    assert c.post(f"/actions/{act['action_id']}/approve", headers=H("analyst.demo"), json={}).status_code == 403
    assert c.post(f"/actions/{act['action_id']}/approve", headers=H("opsmgr.demo"), json={"note": "ok"}).json()["status"] == "approved"
    assert c.post("/actions/ACT-NOPE/approve", headers=H("opsmgr.demo"), json={}).status_code == 404


def test_bad_period_is_400():
    assert c.get("/kpis/sla-breach-rate?period=1999Q1", headers=H("exec.demo")).status_code == 400
