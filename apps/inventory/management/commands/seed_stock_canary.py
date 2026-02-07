from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce

from apps.tenancy.models import Company
from apps.inventory.constants import StockMovementType, StockSourceType
from apps.inventory.models import Part, StockLedgerEntry


@dataclass(frozen=True)
class CanarySpec:
    company_name: str = "Demo Co"
    part_no: str = "RM-TEST-001"
    part_name: str = "Canary Raw Material"
    target_qty: Decimal = Decimal("10.000000")
    unit_cost: Decimal = Decimal("5.0000")


SPEC = CanarySpec()


def _sum_qty(qs) -> Decimal:
    return qs.aggregate(t=Coalesce(Sum("qty"), Decimal("0")))["t"]


def _available(company_id, part_id) -> Decimal:
    qs = StockLedgerEntry.objects.filter(company_id=company_id, part_id=part_id)

    in_q = _sum_qty(qs.filter(movement_type=StockMovementType.IN))
    out_q = _sum_qty(qs.filter(movement_type=StockMovementType.OUT))
    adj_q = _sum_qty(qs.filter(movement_type=StockMovementType.ADJUSTMENT))

    return (in_q - out_q) + adj_q


class Command(BaseCommand):
    help = "Seed deterministic canary for dev (idempotent + append-only; optional normalize-to-target)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--normalize-to-target",
            action="store_true",
            help="Append-only normalize AVAILABLE qty to target via adjustment entry.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        normalize = bool(options.get("normalize_to_target"))

        try:
            c = Company.objects.get(name=SPEC.company_name)
        except Company.DoesNotExist as e:
            raise ValidationError(f"BLOCKER: Company not found: {SPEC.company_name}") from e

        p, _ = Part.objects.get_or_create(
            company_id=c.id,
            part_no=SPEC.part_no,
            defaults={
                "name": SPEC.part_name,
                "part_type": Part.PartType.RAW_MATERIAL,
                "procurement_strategy": Part.ProcurementStrategy.BUY,
            },
        )

        available = _available(company_id=c.id, part_id=p.id)

        # NORMALIZE: available -> target (append-only adjustment)
        if normalize:
            delta = SPEC.target_qty - available

            if delta == Decimal("0"):
                self.stdout.write(
                    self.style.SUCCESS(
                        f"OK: canary already normalized (idempotent). available={available} target={SPEC.target_qty}"
                    )
                )
                return

            # Note: source_type enum has only PURCHASE/PRODUCTION; we tag CANARY in source_ref
            source_ref = f"CANARY:{SPEC.part_no}:NORMALIZE:{uuid4()}"

            StockLedgerEntry.objects.create(
                id=uuid4(),
                company_id=c.id,
                part_id=p.id,
                movement_type=StockMovementType.ADJUSTMENT,
                source_type=StockSourceType.PURCHASE,
                source_ref=source_ref,
                qty=delta,
                unit_cost=SPEC.unit_cost,
                transaction_value=(delta * SPEC.unit_cost),
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"OK: canary normalized. available={available} target={SPEC.target_qty} delta={delta}"
                )
            )
            return

        # SEED: if below target, top-up with IN purchase (append-only)
        if available >= SPEC.target_qty:
            self.stdout.write(
                self.style.SUCCESS(
                    f"OK: canary already seeded (idempotent). available={available} target={SPEC.target_qty}"
                )
            )
            return

        topup = SPEC.target_qty - available
        source_ref = f"CANARY:{SPEC.part_no}:SEED:{uuid4()}"

        StockLedgerEntry.objects.create(
            id=uuid4(),
            company_id=c.id,
            part_id=p.id,
            movement_type=StockMovementType.IN,
            source_type=StockSourceType.PURCHASE,
            source_ref=source_ref,
            qty=topup,
            unit_cost=SPEC.unit_cost,
            transaction_value=(topup * SPEC.unit_cost),
        )

        self.stdout.write(self.style.SUCCESS(f"OK: seeded canary ledger entry. topup={topup}"))
