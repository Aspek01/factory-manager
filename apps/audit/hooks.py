from __future__ import annotations

from django.core.exceptions import ValidationError

from .context import AUDIT_EMIT_ALLOWED
from .events import assert_event_registered
from .guards import run_guards
from .models import AuditEvent


def emit_audit_event(*, event_name: str, payload: dict, context, actor_id=None):
    # Registry enforcement (non-forgettable): unknown event => hard fail
    try:
        assert_event_registered(event_name)
    except Exception as exc:
        # Keep the failure explicitly "spec/governance" shaped (not PermissionDenied)
        raise ValidationError(
            f"Unknown audit event '{event_name}'. Register it in apps.audit.events."
        ) from exc

    run_guards(event_name=event_name, payload=payload, context=context)

    token = AUDIT_EMIT_ALLOWED.set(True)
    try:
        return AuditEvent.objects.create(
            event_name=event_name,
            company_id=context.company_id,
            actor_id=actor_id,
            payload=payload or {},
        )
    finally:
        AUDIT_EMIT_ALLOWED.reset(token)


# --- COMPAT SHIM (tenancy middleware expects audit_event) ---
def audit_event(*, event_name: str, payload: dict, context, actor_id=None):
    return emit_audit_event(
        event_name=event_name,
        payload=payload,
        context=context,
        actor_id=actor_id,
    )
