from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.inventory.models import Part, StockLedgerEntry


class StockLedgerReverseGuardsTests(TestCase):
    def setUp(self) -> None:
        self.company_id = uuid4()

        self.part = Part.objects.create(
            company_id=self.company_id,
            part_no="RM-001",
            name="Raw Material 001",
            part_type=Part.PartType.RAW_MATERIAL,
            procurement_strategy=Part.ProcurementStrategy.BUY,
            is_saleable=False,
            standard_cost=None,
        )

    def _in(self, *, qty: str, unit_cost: str, source_type: str, source_ref: dict | None = None) -> StockLedgerEntry:
        return StockLedgerEntry.objects.create(
            company_id=self.company_id,
            part=self.part,
            movement_type=StockLedgerEntry.MovementType.IN,
            source_type=source_type,
            qty=Decimal(qty),
            unit_cost=Decimal(unit_cost),
            reference_price=None,
            source_ref=source_ref or {},
        )

    def test_reverse_of_same_original_twice_is_blocked(self):
        # Seed stock so reverse OUT won't trip negative-stock
        self._in(qty="10", unit_cost="1.0000", source_type=StockLedgerEntry.SourceType.PURCHASE)

        orig = self._in(qty="5", unit_cost="1.0000", source_type=StockLedgerEntry.SourceType.PURCHASE)

        # First reverse: OK
        r1 = StockLedgerEntry.objects.create(
            company_id=self.company_id,
            part=self.part,
            movement_type=StockLedgerEntry.MovementType.OUT,
            source_type=StockLedgerEntry.SourceType.ADJUSTMENT,
            qty=Decimal("5"),
            unit_cost=Decimal("1.0000"),
            reference_price=None,
            source_ref={"reason": "correction"},
            reverse_of=orig,
        )
        self.assertIsNotNone(r1.id)

        # Second reverse: must fail-closed
        r2 = StockLedgerEntry(
            company_id=self.company_id,
            part=self.part,
            movement_type=StockLedgerEntry.MovementType.OUT,
            source_type=StockLedgerEntry.SourceType.ADJUSTMENT,
            qty=Decimal("5"),
            unit_cost=Decimal("1.0000"),
            reference_price=None,
            source_ref={"reason": "correction-2"},
            reverse_of=orig,
        )
        with self.assertRaises(ValidationError) as ctx:
            r2.save()

        self.assertIn("reverse_of already has a reverse entry", str(ctx.exception))

    def test_reverse_logical_key_includes_reverse_of(self):
        """
        D-3.29: reverse_of is included in the v1 logical key.
        This prevents a reverse write from collapsing into an unrelated adjustment row
        that happens to have the same qty/unit_cost/source_ref/etc.
        """
        # Seed stock so all OUT writes remain non-negative
        self._in(qty="10", unit_cost="1.0000", source_type=StockLedgerEntry.SourceType.PURCHASE)

        orig = self._in(qty="5", unit_cost="1.0000", source_type=StockLedgerEntry.SourceType.PURCHASE)

        # Unrelated adjustment OUT with same payload-shape (reverse_of=None)
        adj = StockLedgerEntry.objects.create(
            company_id=self.company_id,
            part=self.part,
            movement_type=StockLedgerEntry.MovementType.OUT,
            source_type=StockLedgerEntry.SourceType.ADJUSTMENT,
            qty=Decimal("5"),
            unit_cost=Decimal("1.0000"),
            reference_price=None,
            source_ref={"reason": "manual-adjust"},
            reverse_of=None,
        )

        # Reverse OUT with same qty/unit_cost/source_ref-ish but reverse_of set to orig
        rev = StockLedgerEntry.objects.create(
            company_id=self.company_id,
            part=self.part,
            movement_type=StockLedgerEntry.MovementType.OUT,
            source_type=StockLedgerEntry.SourceType.ADJUSTMENT,
            qty=Decimal("5"),
            unit_cost=Decimal("1.0000"),
            reference_price=None,
            source_ref={"reason": "manual-adjust"},
            reverse_of=orig,
        )

        self.assertNotEqual(adj.id, rev.id)

        # Sanity: both entries exist, distinct
        self.assertEqual(
            StockLedgerEntry.objects.filter(company_id=self.company_id, source_type=StockLedgerEntry.SourceType.ADJUSTMENT).count(),
            2,
        )

    def test_reverse_requires_source_type_adjustment(self):
        # Seed stock
        self._in(qty="10", unit_cost="1.0000", source_type=StockLedgerEntry.SourceType.PURCHASE)

        orig = self._in(qty="5", unit_cost="1.0000", source_type=StockLedgerEntry.SourceType.PURCHASE)

        bad = StockLedgerEntry(
            company_id=self.company_id,
            part=self.part,
            movement_type=StockLedgerEntry.MovementType.OUT,
            source_type=StockLedgerEntry.SourceType.SALES,  # not allowed for reverse entries
            qty=Decimal("5"),
            unit_cost=Decimal("1.0000"),
            reference_price=None,
            source_ref={"reason": "should-fail"},
            reverse_of=orig,
        )

        with self.assertRaises(ValidationError) as ctx:
            bad.save()

        self.assertIn("reverse entries must use source_type=adjustment", str(ctx.exception))
