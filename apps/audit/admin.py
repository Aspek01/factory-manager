# apps/audit/admin.py
from django.contrib import admin
from django.core.exceptions import PermissionDenied

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("id", "event_name", "company_id", "actor_id", "created_at")
    list_filter = ("event_name", "created_at")
    search_fields = ("event_name", "company_id", "actor_id")
    ordering = ("-created_at",)
    readonly_fields = ("event_name", "company_id", "actor_id", "payload", "created_at")

    def has_add_permission(self, request):
        # Audit UI’dan insert yasak (yalnýz kod üzerinden emit)
        return False

    def has_change_permission(self, request, obj=None):
        # Append-only: admin üzerinden edit yok
        return False

    def has_delete_permission(self, request, obj=None):
        # Append-only: delete yok
        return False

    def delete_model(self, request, obj):
        raise PermissionDenied("AuditEvent is append-only; delete forbidden")

    def delete_queryset(self, request, queryset):
        raise PermissionDenied("AuditEvent is append-only; bulk delete forbidden")
