from __future__ import annotations

# ============================================================
# Audit Event Registry Delegation (D-3.24)
# ============================================================
# Whitelist kavramı artık YOK.
# Audit event geçerliliği merkezi registry'den (apps.audit.events) doğrulanır.
# Bu dosya sadece guard limitleri ve payload kurallarını tutar.
# ============================================================

# =========================
# Payload Guard Limits
# =========================
# guards.py bu sabitleri import eder
MAX_PAYLOAD_BYTES: int = 8 * 1024  # 8 KB (default)
MAX_PAYLOAD_DEPTH: int = 6
MAX_PAYLOAD_DICT_KEYS: int = 200
MAX_PAYLOAD_LIST_ITEMS: int = 200
MAX_STRING_CHARS: int = 2000

# =========================
# Required Keys Per Event
# =========================
# Event isimleri registry'de tanımlı OLMALI.
# Buradaki yapı sadece payload contract enforcement içindir.
REQUIRED_PAYLOAD_KEYS: dict[str, set[str]] = {
    "rbac.scope.applied": {"user_id", "role", "scope_type", "scope_id"},
    "rbac.scope.revoked": {"user_id", "role", "scope_type", "scope_id"},
    "system.seed.executed": {"by"},

    # inventory.admin intentionally NOT strict:
    # admin list/detail payloads action-specific ve değişken

    # D-3.25: Negative stock block audit (ledger-time, fail-closed)
    "inventory.negative_stock.blocked": {
        "part_id",
        "movement_type",
        "source_type",
        "qty",
        "delta_qty",
        "current_available_qty",
        "projected_available_qty",
        "unit_cost",
        "source_ref",
    },
}

# =========================
# Backward-Compatibility Shim (TEMPORARY)
# =========================
# guards.py veya legacy kod hâlâ AUDIT_EVENT_WHITELIST import ediyorsa
# fail etmemesi için kontrollü bir alias bırakıyoruz.
# GERÇEK doğrulama events.py üzerinden yapılır.
try:
    from .events import EVENTS as _EVENT_REGISTRY

    AUDIT_EVENT_WHITELIST: set[str] = set(_EVENT_REGISTRY.keys())
except Exception:
    # Registry import edilemezse fail-closed davranış guards.py tarafında oluşur
    AUDIT_EVENT_WHITELIST: set[str] = set()
