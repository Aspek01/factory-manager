from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class AuditEventSpec:
    """
    Central, non-forgettable registry for audit events.

    - name: canonical identifier stored in AuditEvent.event_name
    - max_payload_bytes_override: optional per-event payload limit override
    - system_only: if True, should only be emitted by SYSTEM contexts (enforced by guards)
    - notes: maintainer hint
    """

    name: str
    max_payload_bytes_override: Optional[int] = None
    system_only: bool = False
    notes: str = ""


# Single source of truth: ALL audit event names MUST be registered here.
EVENTS: Dict[str, AuditEventSpec] = {
    # --- RBAC / tenancy scope ---
    "rbac.scope.applied": AuditEventSpec(
        name="rbac.scope.applied",
        notes="RBAC scope binding applied for request (middleware).",
    ),
    "rbac.scope.revoked": AuditEventSpec(
        name="rbac.scope.revoked",
        notes="RBAC scope revoked (logout/expire or explicit).",
    ),

    # --- system / bootstrap ---
    "system.seed.executed": AuditEventSpec(
        name="system.seed.executed",
        system_only=False,
        notes="System seed command executed (bootstrap / demo data). Company-scoped.",
    ),

    # --- inventory / admin surface ---
    "inventory.admin": AuditEventSpec(
        name="inventory.admin",
        notes="Admin surface access (list/detail) tenant-safe audit emission.",
    ),
}


def is_event_registered(event_name: str) -> bool:
    return event_name in EVENTS


def get_event_spec(event_name: str) -> Optional[AuditEventSpec]:
    return EVENTS.get(event_name)


def assert_event_registered(event_name: str) -> AuditEventSpec:
    spec = EVENTS.get(event_name)
    if not spec:
        raise KeyError(event_name)
    return spec
