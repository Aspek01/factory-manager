from __future__ import annotations

from uuid import uuid4

from django.db import models
from django.core.exceptions import PermissionDenied

from .guards import guard_event_name, guard_payload
from .context import AUDIT_EMIT_ALLOWED


class AuditEvent(models.Model):
    # Keep UUID PK aligned with existing DB
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    event_name = models.CharField(max_length=128)
    company_id = models.UUIDField()
    actor_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_events"
        indexes = [
            models.Index(fields=["company_id", "created_at"]),
            models.Index(fields=["event_name", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        # Append-only: no updates (only inserts)
        if self.pk and not self._state.adding:
            raise PermissionDenied("AuditEvent is immutable (append-only)")

        # EntryPoint lock: only emit_audit_event() may write
        if not AUDIT_EMIT_ALLOWED.get():
            raise PermissionDenied("AuditEvent writes must go through emit_audit_event()")

        # Model-level guards (bypass-resistant)
        guard_event_name(self.event_name)
        guard_payload(self.event_name, self.payload)

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("AuditEvent delete is forbidden (append-only)")
