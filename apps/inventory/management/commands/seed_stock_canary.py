from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.inventory.models import Part, StockLedgerEntry
from apps.tenancy.models import Company


class Command(BaseCommand):
    help = "Seed deterministic canary StockLedgerEntry for validating PartStockSummary rebuild (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        company_name = "Demo Co"
        part_no = "RM-TEST-001"
        part_name = "Canary Raw Material"

        # Idempotency marker (StockLedgerEntry has no payload field in this repo)
        seed_marker = "CANARY:D-3.5:purchase_in:RM-TEST-001"

        c, _ = Company.objects.get_or_create(name=company_name)

        # Part.name is required (model full_clean guard)
        p, _ = Part.objects.get_or_create(
            company_id=c.id,
            part_no=part_no,
            defaults={
                "name": part_name,
                "part_type": "raw_material",
                "procurement_strategy": "buy",
                "is_saleable": False,
            },
        )

        exists = StockLedgerEntry.objects.filter(
            company_id=c.id,
            part_id=p.id,
            movement_type="in",
            source_type="purchase",
            source_ref=seed_marker,
        ).exists()

        if exists:
            self.stdout.write(self.style.WARNING("OK: canary already seeded (idempotent)"))
            return

        StockLedgerEntry.objects.create(
            company_id=c.id,
            part_id=p.id,
            movement_type="in",
            source_type="purchase",
            qty=Decimal("10"),
            unit_cost=Decimal("5.0000"),
            transaction_value=Decimal("50.0000"),
            source_ref=seed_marker,
        )

        self.stdout.write(self.style.SUCCESS("OK: seeded canary ledger entry"))
