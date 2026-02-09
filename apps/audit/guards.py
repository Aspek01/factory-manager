# apps/audit/guards.py
from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.encoding import force_str

from .constants import (
    MAX_PAYLOAD_BYTES,
    REQUIRED_PAYLOAD_KEYS,
)
from .events import get_event_spec


def guard_event_registry(event_name: str):
    """
    Enforce central audit event registry.
    Unknown events MUST fail closed.
    """
    spec = get_event_spec(event_name)
    if not spec:
        raise ValidationError(
            f"Unknown audit event '{event_name}'. "
            f"Register it in apps.audit.events."
        )
    return spec


def guard_system_only(spec, context):
    """
    If event is marked system_only, context must be SYSTEM-level.
    """
    if not spec.system_only:
        return

    is_system = getattr(context, "is_system", False)
    company_id = getattr(context, "company_id", None)

    # system_only -> require explicit system context OR missing company_id
    if not is_system and company_id is not None:
        raise PermissionDenied(f"Audit event '{spec.name}' is system-only")


def guard_tenant_scope(context):
    """
    Non-system audit events MUST have company_id.
    """
    company_id = getattr(context, "company_id", None)
    is_system = getattr(context, "is_system", False)

    if not is_system and not company_id:
        raise PermissionDenied("Audit context missing company_id")


def guard_payload(event_name: str, payload: dict):
    """
    Payload validation (kept for legacy imports).
    """
    if payload is None:
        payload = {}

    if not isinstance(payload, dict):
        raise ValidationError("Audit payload must be a dict")

    size = len(force_str(payload).encode("utf-8"))
    if size > MAX_PAYLOAD_BYTES:
        raise ValidationError("Audit payload too large")

    required = REQUIRED_PAYLOAD_KEYS.get(event_name)
    if required:
        missing = required - set(payload.keys())
        if missing:
            raise ValidationError(f"Audit payload missing keys: {sorted(missing)}")


def run_guards(*, event_name: str, payload: dict, context):
    """
    Central guard runner.
    Order is intentional and locked:
    1) Registry enforcement
    2) System-only enforcement
    3) Tenant scope enforcement
    4) Payload validation
    """
    spec = guard_event_registry(event_name)
    guard_system_only(spec, context)
    guard_tenant_scope(context)
    guard_payload(event_name, payload)


# ============================================================
# Backward-compat exports (D-3.24)
# ============================================================
# Legacy code imports guard_event_name / guard_payload from here.
# guard_event_name now means "registry enforcement" (NOT whitelist).
def guard_event_name(event_name: str):
    guard_event_registry(event_name)
