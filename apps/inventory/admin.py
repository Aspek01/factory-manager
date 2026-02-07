from __future__ import annotations

import json
from typing import Any

from django.contrib import admin, messages
from django.core.management import call_command
from django.utils.html import format_html

from apps.audit.hooks import audit_event

from .models import BOM, BOMItem, Part, PartStockSummary, StockLedgerEntry


def _resolve_membership_for_admin(request):
    """
    Admin requests should be tenant-safe.
    We attempt to resolve membership using the tenancy RBAC layer.
    Fail-closed: if we cannot resolve, return None.
    """
    try:
        from apps.tenancy.rbac import resolve_membership  # type: ignore
    except Exception:
        return None

    try:
        return resolve_membership(request.user)
    except Exception:
        return None


def _is_system_admin_request(request) -> bool:
    """
    SYSTEM scope visibility:
    - superuser => SYSTEM
    - role-based system_admin => SYSTEM (if membership exposes role)
    """
    if getattr(request.user, "is_superuser", False):
        return True

    membership = _resolve_membership_for_admin(request)
    if not membership:
        return False

    # Be tolerant to different membership shapes.
    role = getattr(membership, "role", None) or getattr(membership, "role_code", None) or getattr(membership, "role_name", None)
    return role == "system_admin"


def _company_id_for_request(request):
    """
    Determine company_id for tenant scoping.
    Fail-closed if unknown.
    """
    membership = _resolve_membership_for_admin(request)
    if membership and getattr(membership, "company_id", None):
        return membership.company_id

    # Some setups may attach company_id to request via middleware.
    if getattr(request, "company_id", None):
        return request.company_id

    return None


def _tenant_filter_queryset(request, qs):
    """
    SYSTEM => all
    non-system => own company only
    fail-closed => none
    """
    if _is_system_admin_request(request):
        return qs
    company_id = _company_id_for_request(request)
    if company_id:
        return qs.filter(company_id=company_id)
    return qs.none()


def _admin_scope_label(request) -> str:
    """
    Best-effort scope label for audit.
    """
    if _is_system_admin_request(request):
        return "SYSTEM"
    membership = _resolve_membership_for_admin(request)
    if membership:
        if getattr(membership, "workstation_id", None):
            return "WORKSTATION"
        if getattr(membership, "section_id", None):
            return "SECTION"
        if getattr(membership, "facility_id", None):
            return "FACILITY"
        if getattr(membership, "company_id", None):
            return "COMPANY"
    return "UNKNOWN"


def _audit_admin_event(request, *, action: str, company_id, meta: dict[str, Any] | None = None) -> None:
    """
    Append-only audit event helper for admin actions/inspections.
    Fail-fast: if audit fails, bubble up (no silent swallow).
    """
    meta = meta or {}
    meta.update(
        {
            "surface": "admin",
            "action": action,
            "scope": _admin_scope_label(request),
            "user_id": str(getattr(request.user, "id", "")) if getattr(request, "user", None) else "",
            "username": getattr(request.user, "username", "") if getattr(request, "user", None) else "",
            "path": getattr(request, "path", ""),
        }
    )

    audit_event(
        company_id=company_id,
        event_type="inventory.admin",
        payload=meta,
    )


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ("part_no", "name", "part_type", "procurement_strategy", "company_id", "updated_at")
    list_filter = ("part_type", "procurement_strategy")
    search_fields = ("part_no", "name")
    readonly_fields = ("last_purchase_price", "created_at", "updated_at")


@admin.register(BOM)
class BOMAdmin(admin.ModelAdmin):
    list_display = ("parent_part", "revision_index", "is_active", "company_id", "created_at")
    list_filter = ("is_active",)
    search_fields = ("parent_part__part_no", "parent_part__name")


@admin.register(BOMItem)
class BOMItemAdmin(admin.ModelAdmin):
    list_display = ("bom", "component_part", "qty_per", "is_direct", "company_id", "created_at")
    list_filter = ("is_direct",)
    search_fields = ("bom__parent_part__part_no", "component_part__part_no")


@admin.register(StockLedgerEntry)
class StockLedgerEntryAdmin(admin.ModelAdmin):
    """
    Read-only ledger inspector (append-only safe).
    - No create/update/delete.
    - Tenant-safe queryset (SYSTEM sees all; others see own company only).
    - Safe presentation for source_ref.
    - Audited inspector access (list + detail).
    """

    list_display = (
        "company_id",
        "created_at",
        "part_link",
        "movement_type",
        "source_type",
        "qty",
        "unit_cost",
        "transaction_value",
        "reference_price",
        "source_ref_preview",
    )
    list_filter = ("movement_type", "source_type", "company_id")
    search_fields = ("part__part_no", "part__name")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    # Hard read-only: no writes
    actions = None

    def changelist_view(self, request, extra_context=None):
        company_id = _company_id_for_request(request)
        # SYSTEM visibility: company_id may be None; still log with None-safe payload
        _audit_admin_event(
            request,
            action="ledger.inspect.list",
            company_id=company_id,
            meta={"model": "StockLedgerEntry"},
        )
        return super().changelist_view(request, extra_context=extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        company_id = _company_id_for_request(request)
        _audit_admin_event(
            request,
            action="ledger.inspect.detail",
            company_id=company_id,
            meta={"model": "StockLedgerEntry", "object_id": object_id},
        )
        return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("part")
        return _tenant_filter_queryset(request, qs)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Allow viewing object detail, forbid saving changes.
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return (
            "id",
            "company_id",
            "part",
            "movement_type",
            "source_type",
            "qty",
            "unit_cost",
            "transaction_value",
            "reference_price",
            "source_ref",
            "created_at",
        )

    def get_fields(self, request, obj=None):
        return (
            "id",
            "company_id",
            "created_at",
            "part",
            "movement_type",
            "source_type",
            "qty",
            "unit_cost",
            "transaction_value",
            "reference_price",
            "source_ref_pretty",
        )

    def source_ref_pretty(self, obj: StockLedgerEntry) -> str:
        try:
            payload = obj.source_ref or {}
            return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
        except Exception:
            return str(obj.source_ref)

    source_ref_pretty.short_description = "source_ref (pretty)"

    def source_ref_preview(self, obj: StockLedgerEntry) -> str:
        # Short, safe preview for list view
        try:
            payload = obj.source_ref or {}
            s = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        except Exception:
            s = str(obj.source_ref)

        return (s[:77] + "...") if len(s) > 80 else s

    source_ref_preview.short_description = "source_ref"

    def part_link(self, obj: StockLedgerEntry) -> str:
        if not obj.part_id:
            return "-"
        url = f"/admin/inventory/part/{obj.part_id}/change/"
        label = getattr(obj.part, "part_no", str(obj.part_id))
        return format_html('<a href="{}">{}</a>', url, label)

    part_link.short_description = "part"

    def save_model(self, request, obj, form, change):
        # Explicitly forbid any attempt to save via admin.
        raise PermissionError("StockLedgerEntry is immutable (admin write forbidden)")

    def delete_model(self, request, obj):
        raise PermissionError("StockLedgerEntry delete is forbidden (admin write forbidden)")

    def delete_queryset(self, request, queryset):
        raise PermissionError("StockLedgerEntry delete is forbidden (admin write forbidden)")


@admin.register(PartStockSummary)
class PartStockSummaryAdmin(admin.ModelAdmin):
    """
    Read-model inspector + guarded rebuild action.
    - Read-only (no manual edits).
    - Tenant-safe list.
    - Guarded rebuild uses management command (read-model only).
    - Audit log for rebuild action.
    """

    list_display = (
        "company_id",
        "part_link",
        "available_qty",
        "weighted_avg_cost",
        "last_purchase_cost",
        "last_production_cost",
        "updated_at",
    )
    search_fields = ("part__part_no", "part__name")
    list_filter = ("company_id",)
    date_hierarchy = "updated_at"
    ordering = ("-updated_at",)

    actions = ["action_rebuild_selected_summaries"]

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("part")
        return _tenant_filter_queryset(request, qs)

    # Hard read-only: no writes (summary is derived)
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Allow viewing object detail, forbid saving changes.
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return (
            "id",
            "company_id",
            "part",
            "available_qty",
            "weighted_avg_cost",
            "last_purchase_cost",
            "last_production_cost",
            "updated_at",
        )

    def part_link(self, obj: PartStockSummary) -> str:
        if not obj.part_id:
            return "-"
        url = f"/admin/inventory/part/{obj.part_id}/change/"
        label = getattr(obj.part, "part_no", str(obj.part_id))
        return format_html('<a href="{}">{}</a>', url, label)

    part_link.short_description = "part"

    @admin.action(description="Rebuild stock summary (selected parts)")
    def action_rebuild_selected_summaries(self, request, queryset):
        """
        Guarded action:
        - Only affects PartStockSummary (read-model).
        - Must be tenant-safe: non-system users can only rebuild within own company.
        - Writes audit event (append-only).
        """
        if not queryset.exists():
            self.message_user(request, "No rows selected.", level=messages.WARNING)
            return

        # Tenant safety: filter to allowed scope again (fail-closed)
        safe_qs = _tenant_filter_queryset(request, queryset)
        if not safe_qs.exists():
            self.message_user(request, "No rows in your allowed scope.", level=messages.ERROR)
            return

        # Ensure single-company selection for non-system users
        company_ids = list(safe_qs.values_list("company_id", flat=True).distinct())
        if not _is_system_admin_request(request) and len(company_ids) != 1:
            self.message_user(request, "Selection must belong to exactly one company.", level=messages.ERROR)
            return

        part_ids = list(safe_qs.values_list("part_id", flat=True))
        if not part_ids:
            self.message_user(request, "No parts found for rebuild.", level=messages.WARNING)
            return

        company_id = company_ids[0] if company_ids else _company_id_for_request(request)

        _audit_admin_event(
            request,
            action="stock_summary.rebuild",
            company_id=company_id,
            meta={"model": "PartStockSummary", "parts": [str(pid) for pid in part_ids]},
        )

        # Call management command in-process (admin action).
        # The command must remain read-model only (no ledger writes).
        try:
            call_command("rebuild_stock_summary", "--part-ids", ",".join(str(pid) for pid in part_ids))
        except Exception as exc:
            self.message_user(request, f"Rebuild failed: {exc}", level=messages.ERROR)
            return

        self.message_user(request, f"Rebuild OK. parts={len(part_ids)}", level=messages.SUCCESS)
