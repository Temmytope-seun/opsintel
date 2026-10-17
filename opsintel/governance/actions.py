"""Action workflow: AI or humans propose; an accountable human approves.

States: proposed -> approved | rejected ; approved -> in_progress -> done.
Rules:
  * only roles with can_propose may propose; only can_approve roles may decide
  * segregation of duties: the proposer can never approve their own action
  * every action stores the evidence it was based on, and every transition is audited
  * the assistant has a propose tool and no approve tool
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import httpx

from opsintel import config
from opsintel.governance import audit
from opsintel.governance.rbac import AccessDenied, User

TRANSITIONS = {"proposed": {"approved", "rejected"}, "approved": {"in_progress", "done"}, "in_progress": {"done"}}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _notify(con, recipient: str, subject: str, body: str):
    delivered = 0
    if config.NOTIFY_WEBHOOK_URL:
        try:
            httpx.post(config.NOTIFY_WEBHOOK_URL, json={"text": f"*{subject}*\n{body}"}, timeout=5).raise_for_status()
            delivered = 1
        except httpx.HTTPError:
            delivered = 0
    con.execute("INSERT INTO notifications (created_at, channel, recipient, subject, body, delivered) VALUES (?,?,?,?,?,?)",
                (_now(), "webhook" if config.NOTIFY_WEBHOOK_URL else "outbox", recipient, subject, body, delivered))


def propose(con, user: User, title: str, rationale: str, evidence: list, priority: str = "P3",
            service_id: str | None = None, owner_group: str | None = None, via_assistant: bool = False) -> dict:
    if not user.role.can_propose:
        raise AccessDenied(f"role {user.role.name} cannot propose actions")
    if not evidence:
        raise ValueError("an action must cite at least one piece of evidence")
    if priority not in ("P1", "P2", "P3", "P4"):
        raise ValueError("priority must be P1-P4")
    action_id = "ACT-" + uuid.uuid4().hex[:8].upper()
    con.execute("""INSERT INTO actions (action_id, created_at, created_by, title, rationale, evidence, service_id,
                   owner_group, priority, status) VALUES (?,?,?,?,?,?,?,?,?, 'proposed')""",
                (action_id, _now(), user.user_id, title, rationale, json.dumps(evidence, default=str), service_id,
                 owner_group, priority))
    _notify(con, "role:ops_manager", f"Approval needed: {title}",
            f"{action_id} proposed by {user.full_name}{' via OpsIntel assistant' if via_assistant else ''}. {rationale}")
    con.commit()
    audit.record(con, user.user_id, user.role.name, "action.proposed",
                 {"action_id": action_id, "title": title, "via_assistant": via_assistant, "evidence_count": len(evidence)})
    return get(con, action_id)


def get(con, action_id: str) -> dict:
    row = con.execute("SELECT * FROM actions WHERE action_id=?", (action_id,)).fetchone()
    if row is None:
        raise KeyError(action_id)
    d = dict(row)
    d["evidence"] = json.loads(d["evidence"])
    return d


def list_actions(con, status: str | None = None) -> list[dict]:
    q = "SELECT * FROM actions" + (" WHERE status=?" if status else "") + " ORDER BY created_at DESC"
    rows = con.execute(q, (status,) if status else ()).fetchall()
    return [dict(r) | {"evidence": json.loads(r["evidence"])} for r in rows]


def decide(con, user: User, action_id: str, approve: bool, note: str = "") -> dict:
    act = get(con, action_id)
    if not user.role.can_approve:
        audit.record(con, user.user_id, user.role.name, "action.decision_denied", {"action_id": action_id, "reason": "role"})
        raise AccessDenied(f"role {user.role.name} cannot approve or reject actions")
    if act["created_by"] == user.user_id:
        audit.record(con, user.user_id, user.role.name, "action.decision_denied", {"action_id": action_id, "reason": "segregation_of_duties"})
        raise AccessDenied("segregation of duties: you cannot decide on an action you proposed")
    new = "approved" if approve else "rejected"
    _transition(act, new)
    con.execute("UPDATE actions SET status=?, decided_by=?, decided_at=?, decision_note=? WHERE action_id=?",
                (new, user.user_id, _now(), note, action_id))
    if approve:
        _notify(con, f"group:{act['owner_group'] or 'Service Management Office'}", f"Approved action: {act['title']}",
                f"{action_id} approved by {user.full_name}. Owner group: {act['owner_group']}. {note}")
    con.commit()
    audit.record(con, user.user_id, user.role.name, f"action.{new}", {"action_id": action_id, "note": note})
    return get(con, action_id)


def update_progress(con, user: User, action_id: str, status: str, outcome: str = "") -> dict:
    act = get(con, action_id)
    if not (user.role.can_approve or user.role.can_propose):
        raise AccessDenied(f"role {user.role.name} cannot update actions")
    _transition(act, status)
    con.execute("UPDATE actions SET status=?, outcome=COALESCE(NULLIF(?, ''), outcome) WHERE action_id=?", (status, outcome, action_id))
    con.commit()
    audit.record(con, user.user_id, user.role.name, f"action.{status}", {"action_id": action_id, "outcome": outcome})
    return get(con, action_id)


def _transition(act: dict, new: str):
    if new not in TRANSITIONS.get(act["status"], set()):
        raise ValueError(f"cannot move action from {act['status']} to {new}")
