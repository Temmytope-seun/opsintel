"""Read-only, role-scoped SQL execution for the assistant.

Enforcement is done by the database engine, not by pattern-matching the query text:
  1. read-only connection (mode=ro) + PRAGMA query_only
  2. sqlite3 authorizer: only SELECT/READ on the role's tables (or through an allowed
     view), PII columns denied, functions whitelisted, PRAGMA/ATTACH/writes denied
  3. single statement, SELECT/WITH only, row cap, wall-clock timeout
Results then pass through PII masking and the prompt-injection screen.
"""
from __future__ import annotations

import re
import sqlite3
import time

from opsintel import config, db
from opsintel.ai.injection import screen
from opsintel.governance.pii import mask
from opsintel.governance.rbac import PII_COLUMNS, Role

ALLOWED_FUNCTIONS = {
    "count", "sum", "avg", "min", "max", "total", "round", "abs", "coalesce", "ifnull", "nullif", "iif",
    "lower", "upper", "trim", "substr", "substring", "length", "replace", "instr", "printf", "format",
    "date", "time", "datetime", "julianday", "strftime", "unixepoch", "group_concat", "like", "glob", "typeof",
    "row_number", "rank", "dense_rank", "lag", "lead",
}


class QueryRejected(ValueError):
    pass


def _schema_objects(con) -> set[str]:
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master")} | {"sqlite_master", "sqlite_schema", "sqlite_sequence"}


def _authorizer(role: Role, denials: list, schema: set[str]):
    def auth(action, arg1, arg2, dbname, source):
        if action == sqlite3.SQLITE_SELECT or action == sqlite3.SQLITE_RECURSIVE:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ:
            table, column = arg1, arg2
            if (table, column) in PII_COLUMNS:
                denials.append(f"column {table}.{column} is personal data and not available to the assistant")
                return sqlite3.SQLITE_DENY
            if table in role.tables or (source and source in role.tables):
                return sqlite3.SQLITE_OK
            if table not in schema:  # common table expression / derived table
                return sqlite3.SQLITE_OK
            denials.append(f"table {table} is not available to role {role.name}")
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION:
            if (arg2 or "").lower() in ALLOWED_FUNCTIONS:
                return sqlite3.SQLITE_OK
            denials.append(f"function {arg2} is not permitted")
            return sqlite3.SQLITE_DENY
        denials.append(f"operation code {action} is not permitted (read-only)")
        return sqlite3.SQLITE_DENY
    return auth


def run_query(sql: str, role: Role, limit: int = config.SQL_ROW_LIMIT, timeout_s: float = 3.0) -> dict:
    text = sql.strip().rstrip(";").strip()
    if not re.match(r"(?is)^(select|with)\b", text):
        raise QueryRejected("Only a single SELECT (or WITH ... SELECT) statement is allowed.")
    if ";" in re.sub(r"'(?:[^']|'')*'", "", text):
        raise QueryRejected("Multiple statements are not allowed.")
    con = db.connect(readonly=True)
    denials: list[str] = []
    try:
        con.execute("PRAGMA query_only = ON")
        con.set_authorizer(_authorizer(role, denials, _schema_objects(con)))
        deadline = time.monotonic() + timeout_s
        con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        try:
            cur = con.execute(text)
        except sqlite3.DatabaseError as e:
            reason = "; ".join(dict.fromkeys(denials)) or ("exceeded time limit" if "interrupted" in str(e) else str(e))
            raise QueryRejected(f"Query not permitted or invalid: {reason}") from e
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(limit + 1)
    except sqlite3.OperationalError as e:
        raise QueryRejected(f"Query aborted: {e}") from e
    finally:
        con.close()
    truncated = len(rows) > limit
    records = [dict(zip(cols, r)) for r in rows[:limit]]
    hits: list[str] = []
    records = screen(mask(records), hits)
    return {"sql": text, "columns": cols, "rows": records, "row_count": len(records), "truncated": truncated,
            "injection_screened_values": len(hits)}
