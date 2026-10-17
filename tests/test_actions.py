import pytest

from opsintel.governance import actions
from opsintel.governance.rbac import AccessDenied

EV = [{"evidence_id": "E1", "summary": "test"}]


def test_full_lifecycle_with_segregation_of_duties(con, users):
    a = actions.propose(con, users["analyst.demo"], "Upgrade firmware", "Because", EV, "P2", "SVC-004", "Network Operations")
    assert a["status"] == "proposed"
    with pytest.raises(AccessDenied):
        actions.decide(con, users["analyst.demo"], a["action_id"], True)       # analyst cannot approve
    b = actions.propose(con, users["opsmgr.demo"], "Self-approve test", "x", EV)
    with pytest.raises(AccessDenied, match="segregation"):
        actions.decide(con, users["opsmgr.demo"], b["action_id"], True)        # cannot approve own
    a = actions.decide(con, users["opsmgr.demo"], a["action_id"], True, "go")
    assert a["status"] == "approved" and a["decided_by"] == "opsmgr.demo"
    a = actions.update_progress(con, users["analyst.demo"], a["action_id"], "done", "pilot complete")
    assert a["status"] == "done" and a["outcome"] == "pilot complete"
    with pytest.raises(ValueError):
        actions.decide(con, users["opsmgr2.demo"], a["action_id"], False)      # no transition from done
    events = [r[0] for r in con.execute("SELECT event FROM audit_log WHERE detail LIKE ?", (f"%{a['action_id']}%",))]
    assert {"action.proposed", "action.approved", "action.done", "action.decision_denied"} <= set(events)


def test_role_and_evidence_requirements(con, users):
    with pytest.raises(AccessDenied):
        actions.propose(con, users["desk.demo"], "x", "y", EV)
    with pytest.raises(ValueError):
        actions.propose(con, users["analyst.demo"], "x", "y", [])
