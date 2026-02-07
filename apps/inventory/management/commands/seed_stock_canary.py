from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.inventory.constants import StockMovementType, StockSourceType
from apps.inventory.models import Part, StockLedgerEntry
from apps.tenancy.models import Company


class Command(BaseCommand):
    help = "Seed deterministic canary stock ledger entry for rebuild_stock_summary (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        c = Company.objects.get(name="Demo Co")

        # Part: deterministic key
        p, _ = Part.objects.get_or_create(
            company_id=c.id,
            part_no="RM-TEST-001",
            defaults={
                "name": "Canary Raw Material",
                "part_type": Part.PartType.RAW_MATERIAL,
                "procurement_strategy": Part.ProcurementStrategy.BUY,
            },
        )

        # Idempotency key via existing fields (no payload field exists in ledger)
        exists = StockLedgerEntry.objects.filter(
            company_id=c.id,
            part_id=p.id,
            movement_type=StockMovementType.IN,
            source_type=StockSourceType.PURCHASE,
            source_ref="CANARY:RM-TEST-001:V1",
        ).exists()

        if exists:
            self.stdout.write(self.style.SUCCESS("OK: canary already seeded (idempotent)"))
            return

        StockLedgerEntry.objects.create(
            company_id=c.id,
            part_id=p.id,
            movement_type=StockMovementType.IN,
            source_type=StockSourceType.PURCHASE,
            source_ref="CANARY:RM-TEST-001:V1",
            qty=Decimal("10.000000"),
            unit_cost=Decimal("5.0000"),
            transaction_value=Decimal("50.0000"),
            reference_price=Decimal("5.0000"),
        )

        self.stdout.write(self.style.SUCCESS("OK: seeded canary ledger entry"))
