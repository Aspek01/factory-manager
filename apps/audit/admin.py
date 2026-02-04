from django.contrib import admin
from django.core.exceptions import ValidationError

from apps.audit.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "scope", "company_id", "actor_user_id")
    list_filter = ("scope", "event_type")
    search_fields = ("event_type", "company_id", "actor_user_id")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
