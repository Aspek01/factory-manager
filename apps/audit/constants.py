from __future__ import annotations

# =========================
# Audit Event Whitelist
# =========================
AUDIT_EVENT_WHITELIST: set[str] = {
    "rbac.scope.applied",
    "rbac.scope.revoked",
    "system.seed.executed",
    "inventory.admin",  # D-3.23: Admin surface audit events
}

# =========================
# Payload Guard Limits
# =========================
# NOTE: guards.py MAY import MAX_PAYLOAD_BYTES and possibly other limits.
MAX_PAYLOAD_BYTES: int = 8 * 1024  # 8 KB
MAX_PAYLOAD_DEPTH: int = 6
MAX_PAYLOAD_DICT_KEYS: int = 200
MAX_PAYLOAD_LIST_ITEMS: int = 200
MAX_STRING_CHARS: int = 2000

# =========================
# Required Keys Per Event
# =========================
REQUIRED_PAYLOAD_KEYS: dict[str, set[str]] = {
    "rbac.scope.applied": {"user_id", "role", "scope_type", "scope_id"},
    "rbac.scope.revoked": {"user_id", "role", "scope_type", "scope_id"},
    "system.seed.executed": {"by"},
    # inventory.admin intentionally NOT strict: payload differs by admin action
}
