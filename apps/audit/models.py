from __future__ import annotations

import uuid
from django.core.exceptions import ValidationError
from django.db import models


class AuditEvent(models.Model):
    """
    Append-only audit log.
    LOCKED: update/delete forbidden. Corrections must be a new event.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    company_id = models.UUIDField(null=True, blank=True)  # system events may be null
    actor_user_id = models.IntegerField(null=True, blank=True)

    event_type = models.CharField(max_length=120)
    scope = models.CharField(max_length=32)  # SYSTEM|COMPANY|FACILITY|SECTION|WORKSTATION

    payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_events"
        indexes = [
            models.Index(fields=["company_id", "created_at"]),
            models.Index(fields=["event_type", "created_at"]),
        ]

    def clean(self):
        if not self.event_type:
            raise ValidationError("event_type is required")
        if self.scope not in {"SYSTEM", "COMPANY", "FACILITY", "SECTION", "WORKSTATION"}:
            raise ValidationError("Invalid scope")

    def save(self, *args, **kwargs):
        if self.pk and AuditEvent.objects.filter(pk=self.pk).exists():
            raise ValidationError("AuditEvent is append-only (update forbidden)")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("AuditEvent is append-only (delete forbidden)")
