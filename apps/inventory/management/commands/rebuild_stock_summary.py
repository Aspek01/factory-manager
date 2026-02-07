from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce

from apps.inventory.constants import StockMovementType, StockSourceType
from apps.inventory.models import PartStockSummary, StockLedgerEntry


Q = Decimal("0.0001")


def _q(d: Decimal) -> Decimal:
    return d.quantize(Q, rounding=ROUND_HALF_UP)


class Command(BaseCommand):
    help = "Rebuild PartStockSummary from append-only StockLedgerEntry (deterministic, WAC-only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company-id",
            type=str,
            required=False,
            help="Optional company UUID to rebuild only one company.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("CANARY: rebuild_stock_summary started")

        company_id = options.get("company_id")

        qs = StockLedgerEntry.objects.all()
        if company_id:
            qs = qs.filter(company_id=company_id)

        base = (
            qs.values("company_id", "part_id")
            .annotate(
                in_qty=Coalesce(
                    Sum(
                        Case(
                            When(movement_type=StockMovementType.IN, then=F("qty")),
                            default=Value(Decimal("0")),
                            output_field=DecimalField(),
                        )
                    ),
                    Value(Decimal("0")),
                ),
                out_qty=Coalesce(
                    Sum(
                        Case(
                            When(movement_type=StockMovementType.OUT, then=F("qty")),
                            default=Value(Decimal("0")),
                            output_field=DecimalField(),
                        )
                    ),
                    Value(Decimal("0")),
                ),
                adj_qty=Coalesce(
                    Sum(
                        Case(
                            When(movement_type=StockMovementType.ADJUSTMENT, then=F("qty")),
                            default=Value(Decimal("0")),
                            output_field=DecimalField(),
                        )
                    ),
                    Value(Decimal("0")),
                ),
                in_value=Coalesce(
                    Sum(
                        Case(
                            When(movement_type=StockMovementType.IN, then=F("transaction_value")),
                            default=Value(Decimal("0")),
                            output_field=DecimalField(),
                        )
                    ),
                    Value(Decimal("0")),
                ),
            )
        )

        total = 0
        updated = 0

        for row in base.iterator():
            total += 1
            c_id = row["company_id"]
            p_id = row["part_id"]

            available_qty = (row["in_qty"] - row["out_qty"]) + row["adj_qty"]

            in_qty = row["in_qty"]
            in_value = row["in_value"]

            if in_qty and in_qty != Decimal("0"):
                wac = _q(in_value / in_qty)
            else:
                wac = Decimal("0")

            last_purchase = (
                qs.filter(
                    company_id=c_id,
                    part_id=p_id,
                    movement_type=StockMovementType.IN,
                    source_type=StockSourceType.PURCHASE,
                )
                .order_by("-created_at")
                .values_list("unit_cost", flat=True)
                .first()
            )

            last_production = (
                qs.filter(
                    company_id=c_id,
                    part_id=p_id,
                    movement_type=StockMovementType.IN,
                    source_type=StockSourceType.PRODUCTION,
                )
                .order_by("-created_at")
                .values_list("unit_cost", flat=True)
                .first()
            )

            PartStockSummary.objects.update_or_create(
                company_id=c_id,
                part_id=p_id,
                defaults={
                    "available_qty": available_qty,
                    "weighted_avg_cost": wac,
                    "last_purchase_cost": last_purchase or None,
                    "last_production_cost": last_production or None,
                },
            )
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"OK: rebuilt PartStockSummary. total_parts={total} updated={updated}"))
