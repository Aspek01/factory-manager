# apps/audit/hooks.py
from .models import AuditEvent
from .guards import run_guards

def emit_audit_event(*, event_name: str, payload: dict, context, actor_id=None):
    run_guards(event_name=event_name, payload=payload, context=context)

    return AuditEvent.objects.create(
        event_name=event_name,
        company_id=context.company_id,
        actor_id=actor_id,
        payload=payload or {},
    )
