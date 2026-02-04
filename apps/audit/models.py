# apps/audit/models.py
from django.db import models
from django.core.exceptions import PermissionDenied

class AuditEvent(models.Model):
    event_name = models.CharField(max_length=128)
    company_id = models.UUIDField()
    actor_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["company_id", "created_at"]),
            models.Index(fields=["event_name", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionDenied("AuditEvent is immutable (append-only)")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("AuditEvent delete is forbidden (append-only)")
