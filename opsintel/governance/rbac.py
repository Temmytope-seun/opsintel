"""Role-based access control.

Demo identities are selected by user id (header X-User / UI selector). In a pilot this
maps to SSO group claims (Entra ID / OIDC); the permission model below is unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass

ANALYTIC_TABLES = frozenset({
    "business_units", "services", "sla_policies", "customers_safe", "assets", "incidents", "v_incidents",
    "service_requests", "alerts", "costs", "catalog",
})
# Never readable through the assistant, whatever the role. The DPO accesses these
# through the source system, not through AI tooling.
PII_COLUMNS = frozenset({("customers", "contact_email"), ("customers", "contact_phone"), ("customers", "account_manager")})


@dataclass(frozen=True)
class Role:
    name: str
    tables: frozenset
    doc_levels: frozenset
    can_propose: bool
    can_approve: bool
    can_view_audit: bool
    description: str


ROLES = {
    "executive": Role("executive", ANALYTIC_TABLES, frozenset({"public", "internal", "restricted"}), True, True, True,
                      "Board / director level - all operational and financial data, approves actions"),
    "ops_manager": Role("ops_manager", ANALYTIC_TABLES, frozenset({"public", "internal", "restricted"}), True, True, False,
                        "Head of service operations - approves actions for their area"),
    "analyst": Role("analyst", ANALYTIC_TABLES, frozenset({"public", "internal"}), True, False, False,
                    "Service performance analyst - proposes actions, cannot approve"),
    "service_desk": Role("service_desk", ANALYTIC_TABLES - {"costs"}, frozenset({"public", "internal"}), False, False, False,
                         "Service desk engineer - operational data and runbooks, no financials"),
    "auditor": Role("auditor", ANALYTIC_TABLES, frozenset({"public", "internal", "restricted"}), False, False, True,
                    "Internal audit / DPO - read-only, full audit trail"),
}

DEMO_USERS = [
    ("exec.demo", "Morgan Hale (Operations Director)", "executive"),
    ("opsmgr.demo", "Priya Raman (Head of Service Ops)", "ops_manager"),
    ("opsmgr2.demo", "Tom Ashworth (Network Ops Manager)", "ops_manager"),
    ("analyst.demo", "Sam Quinn (Performance Analyst)", "analyst"),
    ("desk.demo", "Alex Byrne (Service Desk L2)", "service_desk"),
    ("audit.demo", "Jordan Lee (Internal Audit)", "auditor"),
]


class AccessDenied(PermissionError):
    pass


@dataclass(frozen=True)
class User:
    user_id: str
    full_name: str
    role: Role


def seed_users(con) -> None:
    con.executemany("INSERT OR REPLACE INTO users VALUES (?,?,?)", DEMO_USERS)


def get_user(con, user_id: str) -> User:
    row = con.execute("SELECT user_id, full_name, role FROM users WHERE user_id=?", (user_id,)).fetchone()
    if row is None:
        raise AccessDenied(f"unknown user {user_id!r}")
    return User(row[0], row[1], ROLES[row[2]])
