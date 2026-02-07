from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.utils.html import format_html

from apps.audit.hooks import audit_event

from .models import BOM, BOMItem, Part, PartStockSummary, StockLedgerEntry


# =========================
# Tenant resolution helpers
# =========================
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

    role = (
        getattr(membership, "role", None)
        or getattr(membership, "role_code", None)
        or getattr(membership, "role_name", None)
    )
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


# =========================
# Fail-closed policy (D-3.21)
# =========================
def _deny_if_tenant_unresolved(request) -> None:
    """
    Deterministic fail-closed behavior across admin:
    - SYSTEM: allowed
    - non-system: if company_id cannot be resolved => 403
    """
    if _is_system_admin_request(request):
        return
    if not _company_id_for_request(request):
        raise PermissionDenied("Tenant scope unresolved (fail-closed).")


def _ensure_obj_in_tenant_or_raise(request, obj, *, company_field: str = "company_id") -> None:
    """
    Object-level guard for admin detail pages.
    - SYSTEM: always allowed.
    - Non-system: requires resolved company_id and object.company_id must match.
    """
    if obj is None:
        return

    if _is_system_admin_request(request):
        return

    req_company_id = _company_id_for_request(request)
    if not req_company_id:
        raise PermissionDenied("Tenant scope unresolved (fail-closed).")

    obj_company_id = getattr(obj, company_field, None)
    if obj_company_id != req_company_id:
        raise PermissionDenied("Cross-company admin access is forbidden.")


def _safe_admin_change_url_for_obj(request, *, model: str, obj_id, obj_company_id) -> str | None:
    """
    Prevent cross-tenant admin link leakage.
    Returns None if link must not be rendered for this request.
    """
    if not obj_id:
        return None

    if _is_system_admin_request(request):
        return f"/admin/inventory/{model}/{obj_id}/change/"

    req_company_id = _company_id_for_request(request)
    if not req_company_id:
        return None

    if obj_company_id != req_company_id:
        return None

    return f"/admin/inventory/{model}/{obj_id}/change/"


# =========================
# Audit helpers (compatible with audit_event signature)
# =========================
def _build_audit_context(company_id):
    """
    Build audit context compatible with apps.audit.hooks.emit_audit_event.
    Minimal requirement: context.company_id
    """
    if not company_id:
        return None

    try:
        from apps.audit.context import AuditContext  # type: ignore

        try:
            return AuditContext(company_id=company_id)
        except TypeError:
            return SimpleNamespace(company_id=company_id)
    except Exception:
        return SimpleNamespace(company_id=company_id)


def _audit_admin_event(
    request,
    *,
    action: str,
    company_id,
    meta: dict[str, Any] | None = None,
) -> None:
    """
    Append-only audit event helper for admin actions/inspections.
    IMPORTANT:
    - audit_event(...) requires (event_name, payload, context, actor_id)
    - If company_id cannot be resolved, skip emit to avoid DB NOT NULL breaks.
    """
    ctx = _build_audit_context(company_id)
    if ctx is None:
        return

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

    actor_id = getattr(request.user, "id", None) if getattr(request, "user", None) else None
    audit_event(
        event_name="inventory.admin",
        payload=meta,
        context=ctx,
        actor_id=actor_id,
    )


# =========================
# Admin registrations
# =========================
@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ("part_no", "name", "part_type", "procurement_strategy", "company_id", "updated_at")
    list_filter = ("part_type", "procurement_strategy")
    search_fields = ("part_no", "name")
    readonly_fields = ("last_purchase_price", "created_at", "updated_at")
    ordering = ("part_no",)

    def get_queryset(self, request):
        return _tenant_filter_queryset(request, super().get_queryset(request))

    def get_object(self, request, object_id, from_field=None):
        _deny_if_tenant_unresolved(request)
        obj = super().get_object(request, object_id, from_field=from_field)
        _ensure_obj_in_tenant_or_raise(request, obj, company_field="company_id")
        return obj

    def change_view(self, request, object_id, form_url="", extra_context=None):
        _deny_if_tenant_unresolved(request)
        return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)


@admin.register(BOM)
class BOMAdmin(admin.ModelAdmin):
    list_display = ("parent_part_link", "revision_index", "is_active", "company_id", "created_at")
    list_filter = ("is_active", "company_id")
    search_fields = ("parent_part__part_no", "parent_part__name")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("parent_part")
        return _tenant_filter_queryset(request, qs)

    def get_object(self, request, object_id, from_field=None):
        _deny_if_tenant_unresolved(request)
        obj = super().get_object(request, object_id, from_field=from_field)
        _ensure_obj_in_tenant_or_raise(request, obj, company_field="company_id")
        return obj

    def parent_part_link(self, obj: BOM) -> str:
        if not obj.parent_part_id:
            return "-"

        request = getattr(self, "_request", None)
        label = getattr(obj.parent_part, "part_no", str(obj.parent_part_id))
        if request is None:
            return label

        url = _safe_admin_change_url_for_obj(
            request,
            model="part",
            obj_id=obj.parent_part_id,
            obj_company_id=getattr(obj.parent_part, "company_id", None),
        )
        if not url:
            return label
        return format_html('<a href="{}">{}</a>', url, label)

    parent_part_link.short_description = "parent_part"

    def changelist_view(self, request, extra_context=None):
        self._request = request
        return super().changelist_view(request, extra_context=extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        self._request = request
        _deny_if_tenant_unresolved(request)
        return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)


@admin.register(BOMItem)
class BOMItemAdmin(admin.ModelAdmin):
    list_display = ("bom_link", "component_part_link", "qty_per", "is_direct", "company_id", "created_at")
    list_filter = ("is_direct", "company_id")
    search_fields = ("bom__parent_part__part_no", "component_part__part_no")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("bom", "component_part", "bom__parent_part")
        return _tenant_filter_queryset(request, qs)

    def get_object(self, request, object_id, from_field=None):
        _deny_if_tenant_unresolved(request)
        obj = super().get_object(request, object_id, from_field=from_field)
        _ensure_obj_in_tenant_or_raise(request, obj, company_field="company_id")
        return obj

    def bom_link(self, obj: BOMItem) -> str:
        if not obj.bom_id:
            return "-"

        request = getattr(self, "_request", None)
        label = (
            f"BOM:{getattr(getattr(obj.bom, 'parent_part', None), 'part_no', '')} "
            f"rev:{getattr(obj.bom, 'revision_index', '')}"
        ).strip()
        label = label if label != "BOM: rev:" else str(obj.bom_id)

        if request is None:
            return label

        url = _safe_admin_change_url_for_obj(
            request,
            model="bom",
            obj_id=obj.bom_id,
            obj_company_id=getattr(obj.bom, "company_id", None),
        )
        if not url:
            return label
        return format_html('<a href="{}">{}</a>', url, label)

    bom_link.short_description = "bom"

    def component_part_link(self, obj: BOMItem) -> str:
        if not obj.component_part_id:
            return "-"

        request = getattr(self, "_request", None)
        label = getattr(obj.component_part, "part_no", str(obj.component_part_id))
        if request is None:
            return label

        url = _safe_admin_change_url_for_obj(
            request,
            model="part",
            obj_id=obj.component_part_id,
            obj_company_id=getattr(obj.component_part, "company_id", None),
        )
        if not url:
            return label
        return format_html('<a href="{}">{}</a>', url, label)

    component_part_link.short_description = "component_part"

    def changelist_view(self, request, extra_context=None):
        self._request = request
        return super().changelist_view(request, extra_context=extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        self._request = request
        _deny_if_tenant_unresolved(request)
        return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)


@admin.register(StockLedgerEntry)
class StockLedgerEntryAdmin(admin.ModelAdmin):
    """
    Read-only ledger inspector (append-only safe).
    - No create/update/delete.
    - Tenant-safe queryset (SYSTEM sees all; others see own company only).
    - Safe presentation for source_ref.
    - Audited inspector access (list + detail) when company_id is resolvable.
    - Object-level guard on detail view.
    - No cross-tenant Part link leakage.
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

    actions = None

    def changelist_view(self, request, extra_context=None):
        self._request = request
        company_id = _company_id_for_request(request)
        _audit_admin_event(
            request,
            action="ledger.inspect.list",
            company_id=company_id,
            meta={"model": "StockLedgerEntry"},
        )
        return super().changelist_view(request, extra_context=extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        self._request = request
        _deny_if_tenant_unresolved(request)
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

    def get_object(self, request, object_id, from_field=None):
        _deny_if_tenant_unresolved(request)
        obj = super().get_object(request, object_id, from_field=from_field)
        _ensure_obj_in_tenant_or_raise(request, obj, company_field="company_id")
        return obj

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
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

        request = getattr(self, "_request", None)
        label = getattr(obj.part, "part_no", str(obj.part_id))
        if request is None:
            return label

        url = _safe_admin_change_url_for_obj(
            request,
            model="part",
            obj_id=obj.part_id,
            obj_company_id=getattr(obj.part, "company_id", None),
        )
        if not url:
            return label
        return format_html('<a href="{}">{}</a>', url, label)

    part_link.short_description = "part"

    def save_model(self, request, obj, form, change):
        raise PermissionDenied("StockLedgerEntry is immutable (admin write forbidden)")

    def delete_model(self, request, obj):
        raise PermissionDenied("StockLedgerEntry delete is forbidden (admin write forbidden)")

    def delete_queryset(self, request, queryset):
        raise PermissionDenied("StockLedgerEntry delete is forbidden (admin write forbidden)")


@admin.register(PartStockSummary)
class PartStockSummaryAdmin(admin.ModelAdmin):
    """
    Read-model inspector + guarded rebuild action.
    - Read-only (no manual edits).
    - Tenant-safe list.
    - Guarded rebuild uses management command (read-model only).
    - Audit log for rebuild action when company_id is resolvable.
    - Object-level guard on detail view.
    - No cross-tenant Part link leakage.
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

    def get_object(self, request, object_id, from_field=None):
        _deny_if_tenant_unresolved(request)
        obj = super().get_object(request, object_id, from_field=from_field)
        _ensure_obj_in_tenant_or_raise(request, obj, company_field="company_id")
        return obj

    def change_view(self, request, object_id, form_url="", extra_context=None):
        self._request = request
        _deny_if_tenant_unresolved(request)
        return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
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

        request = getattr(self, "_request", None)
        label = getattr(obj.part, "part_no", str(obj.part_id))
        if request is None:
            return label

        url = _safe_admin_change_url_for_obj(
            request,
            model="part",
            obj_id=obj.part_id,
            obj_company_id=getattr(obj.part, "company_id", None),
        )
        if not url:
            return label
        return format_html('<a href="{}">{}</a>', url, label)

    part_link.short_description = "part"

    def changelist_view(self, request, extra_context=None):
        self._request = request
        return super().changelist_view(request, extra_context=extra_context)

    @admin.action(description="Rebuild stock summary (selected parts)")
    def action_rebuild_selected_summaries(self, request, queryset):
        if not queryset.exists():
            self.message_user(request, "No rows selected.", level=messages.WARNING)
            return

        safe_qs = _tenant_filter_queryset(request, queryset)
        if not safe_qs.exists():
            self.message_user(request, "No rows in your allowed scope.", level=messages.ERROR)
            return

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

        try:
            call_command("rebuild_stock_summary", "--part-ids", ",".join(str(pid) for pid in part_ids))
        except Exception as exc:
            self.message_user(request, f"Rebuild failed: {exc}", level=messages.ERROR)
            return

        self.message_user(request, f"Rebuild OK. parts={len(part_ids)}", level=messages.SUCCESS)
