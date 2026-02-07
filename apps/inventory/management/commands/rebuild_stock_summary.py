from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce

from apps.inventory.models import PartStockSummary, StockLedgerEntry


Q = Decimal("0.0001")


def _q(d: Decimal) -> Decimal:
    return d.quantize(Q, rounding=ROUND_HALF_UP)


def _get_field_name(model, candidates: list[str]) -> str:
    names = {f.name for f in model._meta.fields}
    for c in candidates:
        if c in names:
            return c
    raise RuntimeError(
        f"BLOCKER: expected field not found. "
        f"candidates={candidates} model={model.__name__} fields={sorted(names)}"
    )


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
        # CANARY: deterministic visibility
        self.stdout.write("CANARY: rebuild_stock_summary started")

        company_id = options.get("company_id")

        movement_type_f = _get_field_name(StockLedgerEntry, ["movement_type"])
        source_type_f = _get_field_name(StockLedgerEntry, ["source_type"])
        qty_f = _get_field_name(StockLedgerEntry, ["qty", "quantity"])
        unit_cost_f = _get_field_name(StockLedgerEntry, ["unit_cost"])
        tx_value_f = _get_field_name(StockLedgerEntry, ["transaction_value", "value"])
        created_at_f = _get_field_name(
            StockLedgerEntry, ["created_at", "created", "timestamp"]
        )

        qs = StockLedgerEntry.objects.all()
        if company_id:
            qs = qs.filter(company_id=company_id)

        # Only "in" contributes to WAC, and only these source types are cost-contributing (LOCKED)
        cost_in_sources = {"purchase", "production", "subcontracting_receive"}

        base = (
            qs.values("company_id", "part_id")
            .annotate(
                in_qty=Coalesce(
                    Sum(
                        Case(
                            When(**{movement_type_f: "in"}, then=F(qty_f)),
                            default=Value(Decimal("0")),
                            output_field=DecimalField(),
                        )
                    ),
                    Value(Decimal("0")),
                ),
                out_qty=Coalesce(
                    Sum(
                        Case(
                            When(**{movement_type_f: "out"}, then=F(qty_f)),
                            default=Value(Decimal("0")),
                            output_field=DecimalField(),
                        )
                    ),
                    Value(Decimal("0")),
                ),
                adj_qty=Coalesce(
                    Sum(
                        Case(
                            When(**{movement_type_f: "adjustment"}, then=F(qty_f)),
                            default=Value(Decimal("0")),
                            output_field=DecimalField(),
                        )
                    ),
                    Value(Decimal("0")),
                ),
                # WAC numerator: sum(transaction_value) only for cost-contributing ins
                in_value=Coalesce(
                    Sum(
                        Case(
                            When(
                                **{
                                    movement_type_f: "in",
                                    f"{source_type_f}__in": list(cost_in_sources),
                                },
                                then=F(tx_value_f),
                            ),
                            default=Value(Decimal("0")),
                            output_field=DecimalField(),
                        )
                    ),
                    Value(Decimal("0")),
                ),
                # WAC denominator: sum(qty) only for cost-contributing ins
                in_cost_qty=Coalesce(
                    Sum(
                        Case(
                            When(
                                **{
                                    movement_type_f: "in",
                                    f"{source_type_f}__in": list(cost_in_sources),
                                },
                                then=F(qty_f),
                            ),
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

            in_cost_qty = row["in_cost_qty"]
            in_value = row["in_value"]

            if in_cost_qty and in_cost_qty != Decimal("0"):
                wac = _q(in_value / in_cost_qty)
            else:
                wac = Decimal("0")

            last_purchase = (
                qs.filter(
                    company_id=c_id,
                    part_id=p_id,
                    **{movement_type_f: "in"},
                    **{source_type_f: "purchase"},
                )
                .order_by(f"-{created_at_f}")
                .values_list(unit_cost_f, flat=True)
                .first()
            )

            last_production = (
                qs.filter(
                    company_id=c_id,
                    part_id=p_id,
                    **{movement_type_f: "in"},
                    **{source_type_f: "production"},
                )
                .order_by(f"-{created_at_f}")
                .values_list(unit_cost_f, flat=True)
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

        self.stdout.write(
            self.style.SUCCESS(
                f"OK: rebuilt PartStockSummary. total_parts={total} updated={updated}"
            )
        )
