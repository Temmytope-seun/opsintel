"""Tamper-evident audit log: every entry is hash-chained to the previous one."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

GENESIS = "0" * 64


def _digest(prev_hash: str, ts: str, user_id: str, role: str, event: str, detail: str) -> str:
    return hashlib.sha256("|".join([prev_hash, ts, user_id, role, event, detail]).encode()).hexdigest()


def record(con, user_id: str, role: str, event: str, detail: dict) -> int:
    ts = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    payload = json.dumps(detail, sort_keys=True, default=str)
    row = con.execute("SELECT hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
    prev = row[0] if row else GENESIS
    h = _digest(prev, ts, user_id, role, event, payload)
    cur = con.execute("INSERT INTO audit_log (ts,user_id,role,event,detail,prev_hash,hash) VALUES (?,?,?,?,?,?,?)",
                      (ts, user_id, role, event, payload, prev, h))
    con.commit()
    return cur.lastrowid


def verify(con) -> tuple[bool, int | None]:
    """Return (ok, first_bad_seq)."""
    prev = GENESIS
    for seq, ts, user_id, role, event, detail, prev_hash, h in con.execute(
            "SELECT seq, ts, user_id, role, event, detail, prev_hash, hash FROM audit_log ORDER BY seq"):
        if prev_hash != prev or _digest(prev_hash, ts, user_id, role, event, detail) != h:
            return False, seq
        prev = h
    return True, None
