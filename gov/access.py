"""Role-scoped access control (MASTER_PLAN G.1).

Who sees what. A plant analyst sees only their scope; the CFO sees finance; the CEO sees
all. Scopes are matched against the caller's role scope from config.yaml, supporting exact,
prefix wildcard (finance:*), and the all wildcard (*).
"""
from __future__ import annotations


def can_access(role: str, scope: str, cfg: dict) -> bool:
    role_scope = cfg.get("roles", {}).get(role, {}).get("scope", "")
    if not role_scope:
        return False
    if role_scope == "*" or role_scope == scope:
        return True
    if role_scope.endswith(":*") and scope.startswith(role_scope[:-1]):
        return True
    return False
