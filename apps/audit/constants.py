# apps/audit/constants.py

AUDIT_EVENT_WHITELIST = {
    "rbac.scope.applied",
    "rbac.scope.revoked",
    "system.seed.executed",
}

MAX_PAYLOAD_BYTES = 8 * 1024  # 8 KB

REQUIRED_PAYLOAD_KEYS = {
    "rbac.scope.applied": {"user_id", "role", "scope_type", "scope_id"},
    "rbac.scope.revoked": {"user_id", "role", "scope_type", "scope_id"},
    "system.seed.executed": {"by"},
}
