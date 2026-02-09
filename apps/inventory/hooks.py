# apps/inventory/hooks.py
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction


def on_ledger_insert(*, entry) -> None:
    """
    Update PartStockSummary after StockLedgerEntry insert.

    LOCKED invariants:
    - No model imports at module import time (prevents circular imports).
    - Uses select_for_update for deterministic updates.
    - Read-model must be derivable from ledger, but MUST NOT introduce new semantics.

    D-3.30:
    - reverse_of entries are a correction lane:
      * apply ONLY stock delta (qty impact)
      * DO NOT update weighted_avg_cost (WAC)
      * DO NOT update last_purchase_cost / last_production_cost
    """
    from apps.inventory.models import PartStockSummary, StockLedgerEntry  # local import

    if not isinstance(entry, StockLedgerEntry):
        raise ValidationError("on_ledger_insert: invalid entry type")

    if entry.qty is None or entry.unit_cost is None:
        raise ValidationError("on_ledger_insert: qty/unit_cost required")

    company_id: UUID = entry.company_id
    part_id: UUID = entry.part_id

    qty = Decimal(entry.qty)
    unit_cost = Decimal(entry.unit_cost)

    def _delta_qty() -> Decimal:
        if entry.movement_type == "in":
            return qty
        if entry.movement_type == "out":
            return qty * Decimal("-1")
        if entry.movement_type == "adjustment":
            # adjustment is signed by design
            return qty
        raise ValidationError(f"Unknown movement_type: {entry.movement_type}")

    with transaction.atomic():
        summary, _ = PartStockSummary.objects.select_for_update().get_or_create(
            company_id=company_id,
            part_id=part_id,
            defaults={
                "available_qty": Decimal("0"),
                "weighted_avg_cost": Decimal("0"),
            },
        )

        old_qty = Decimal(summary.available_qty)
        old_wac = Decimal(summary.weighted_avg_cost)

        delta = _delta_qty()
        new_qty = old_qty + delta

        # Read-model must not go negative (ledger-time guard should already prevent this)
        if new_qty < 0:
            raise ValidationError("Stock summary cannot go negative")

        # Always apply quantity delta
        summary.available_qty = new_qty

        # D-3.30: reverse lane => do NOT touch costing fields (pure correction of stock)
        if entry.reverse_of_id:
            summary.save()
            return

        # Normal lane: WAC updates only on positive IN qty
        # (OUT and negative adjustments must not affect WAC)
        if entry.movement_type == "in" and qty > 0:
            total_value = (old_qty * old_wac) + (qty * unit_cost)
            summary.weighted_avg_cost = (total_value / new_qty) if new_qty != 0 else Decimal("0")

            # Last cost lanes (only for real inflows, not reverse)
            if entry.source_type == "purchase":
                summary.last_purchase_cost = unit_cost
            if entry.source_type == "production":
                summary.last_production_cost = unit_cost

        summary.save()
