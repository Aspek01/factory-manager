from __future__ import annotations

from django.contrib import admin

from .models import BOM, BOMItem, Part, PartStockSummary, StockLedgerEntry


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
    list_display = ("part", "movement_type", "source_type", "qty", "unit_cost", "transaction_value", "company_id", "created_at")
    list_filter = ("movement_type", "source_type")
    search_fields = ("part__part_no",)


@admin.register(PartStockSummary)
class PartStockSummaryAdmin(admin.ModelAdmin):
    list_display = ("part", "available_qty", "weighted_avg_cost", "company_id", "updated_at")
    search_fields = ("part__part_no", "part__name")
