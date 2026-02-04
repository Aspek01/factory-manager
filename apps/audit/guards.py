# apps/audit/guards.py
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.encoding import force_str

from .constants import (
    AUDIT_EVENT_WHITELIST,
    MAX_PAYLOAD_BYTES,
    REQUIRED_PAYLOAD_KEYS,
)

def guard_event_name(event_name: str):
    if event_name not in AUDIT_EVENT_WHITELIST:
        raise PermissionDenied(f"Audit event not allowed: {event_name}")

def guard_tenant_scope(context):
    company_id = getattr(context, "company_id", None)
    if not company_id:
        raise PermissionDenied("Audit context missing company_id")

def guard_payload(event_name: str, payload: dict):
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
    guard_event_name(event_name)
    guard_tenant_scope(context)
    guard_payload(event_name, payload)
