from __future__ import annotations

from .models import AuditEvent
from .guards import run_guards
from .context import AUDIT_EMIT_ALLOWED


def emit_audit_event(*, event_name: str, payload: dict, context, actor_id=None):
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
