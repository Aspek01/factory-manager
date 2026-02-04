from __future__ import annotations

from apps.audit.models import AuditEvent


def audit_event(
    *,
    company_id=None,
    actor_user_id=None,
    event_type: str,
    scope: str,
    payload: dict | None = None,
):
    AuditEvent.objects.create(
        company_id=company_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        scope=scope,
        payload=payload or {},
    )
