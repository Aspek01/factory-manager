# apps/inventory/models.py
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, models, transaction

from apps.inventory.guards import assert_max_depth, assert_no_circular_bom


class Part(models.Model):
    class PartType(models.TextChoices):
        FINISHED_GOOD = "finished_good", "finished_good"
        SEMI_FINISHED = "semi_finished", "semi_finished"
        RAW_MATERIAL = "raw_material", "raw_material"
        CONSUMABLE = "consumable", "consumable"
        FIXED_ASSET = "fixed_asset", "fixed_asset"

    class ProcurementStrategy(models.TextChoices):
        MAKE = "make", "make"
        BUY = "buy", "buy"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    company_id = models.UUIDField()

    part_no = models.CharField(max_length=64)
    name = models.CharField(max_length=255)

    part_type = models.CharField(max_length=32, choices=PartType.choices)
    procurement_strategy = models.CharField(max_length=8, choices=ProcurementStrategy.choices)

    is_saleable = models.BooleanField(default=False)

    standard_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    last_purchase_price = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Read-only (updated by GR/QC pass flow).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inventory_parts"
        constraints = [
            models.UniqueConstraint(fields=["company_id", "part_no"], name="uq_inventory_part_company_partno"),
        ]
        indexes = [
            models.Index(fields=["company_id", "part_no"]),
            models.Index(fields=["company_id", "part_type"]),
        ]

    def clean(self):
        super().clean()

        # Part type + procurement strategy constraints (LOCKED)
        if self.part_type == self.PartType.FINISHED_GOOD and self.procurement_strategy != self.ProcurementStrategy.MAKE:
            raise ValidationError("finished_good MUST make")

        if self.part_type in {self.PartType.RAW_MATERIAL, self.PartType.CONSUMABLE, self.PartType.FIXED_ASSET}:
            if self.procurement_strategy != self.ProcurementStrategy.BUY:
                raise ValidationError("raw_material/consumable/fixed_asset MUST buy")

        if self.part_type == self.PartType.SEMI_FINISHED:
            if self.procurement_strategy not in {self.ProcurementStrategy.MAKE, self.ProcurementStrategy.BUY}:
                raise ValidationError("semi_finished must be make or buy")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class BOM(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    company_id = models.UUIDField()

    parent_part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name="boms")
    revision_index = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_boms"
        constraints = [
            models.UniqueConstraint(
                fields=["company_id", "parent_part", "revision_index"],
                name="uq_inventory_bom_company_parent_rev",
            ),
        ]
        indexes = [
            models.Index(fields=["company_id", "parent_part"]),
        ]

    def clean(self):
        super().clean()

        if self.parent_part.part_type not in {Part.PartType.FINISHED_GOOD, Part.PartType.SEMI_FINISHED}:
            raise ValidationError("BOM parent must be finished_good or semi_finished")

        # Company boundary safety (fail-fast)
        if self.parent_part.company_id != self.company_id:
            raise ValidationError("company_id mismatch between BOM and parent_part")

    def save(self, *args, **kwargs):
        self.full_clean()
        result = super().save(*args, **kwargs)

        # Post-save graph validation (fail-fast)
        assert_no_circular_bom(self.company_id, self.parent_part_id)
        assert_max_depth(self.company_id, self.parent_part_id)

        return result


class BOMItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    company_id = models.UUIDField()

    bom = models.ForeignKey(BOM, on_delete=models.CASCADE, related_name="items")
    component_part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name="bom_components")

    qty_per = models.DecimalField(max_digits=18, decimal_places=6)
    is_direct = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_bom_items"
        constraints = [
            models.UniqueConstraint(
                fields=["bom", "component_part"],
                name="uq_inventory_bomitem_bom_component",
            ),
        ]
        indexes = [
            models.Index(fields=["company_id", "bom"]),
        ]

    def clean(self):
        super().clean()

        # Component eligibility (LOCKED)
        if self.component_part.part_type in {Part.PartType.FINISHED_GOOD, Part.PartType.FIXED_ASSET}:
            raise ValidationError("BOM component cannot be finished_good or fixed_asset")

        if self.component_part.part_type == Part.PartType.CONSUMABLE and not self.is_direct:
            # Indirect consumables are explicitly out of BOM per spec
            raise ValidationError("Indirect consumables must not be BOM components (set is_direct=True)")

        # Company boundary safety (fail-fast)
        if self.bom.company_id != self.company_id:
            raise ValidationError("company_id mismatch between BOMItem and BOM")
        if self.component_part.company_id != self.company_id:
            raise ValidationError("company_id mismatch between BOMItem and component_part")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class StockLedgerEntry(models.Model):
    class MovementType(models.TextChoices):
        IN = "in", "in"
        OUT = "out", "out"
        ADJUSTMENT = "adjustment", "adjustment"

    class SourceType(models.TextChoices):
        PURCHASE = "purchase", "purchase"
        PRODUCTION = "production", "production"
        SALES = "sales", "sales"
        ADJUSTMENT = "adjustment", "adjustment"
        SUBCONTRACTING_SEND = "subcontracting_send", "subcontracting_send"
        SUBCONTRACTING_RECEIVE = "subcontracting_receive", "subcontracting_receive"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    company_id = models.UUIDField()

    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name="ledger_entries")

    movement_type = models.CharField(max_length=16, choices=MovementType.choices)
    source_type = models.CharField(max_length=32, choices=SourceType.choices)

    qty = models.DecimalField(max_digits=18, decimal_places=6)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4)
    transaction_value = models.DecimalField(max_digits=16, decimal_places=4)

    reference_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    source_ref = models.JSONField(default=dict)

    # v2 idempotency (API event standard) — optional
    idempotency_key = models.CharField(max_length=128, null=True, blank=True)
    idempotency_scope = models.CharField(
        max_length=16,
        null=True,
        blank=True,
        help_text="SYSTEM|COMPANY|FACILITY|SECTION|WORKSTATION (nullable).",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_stock_ledger"
        indexes = [
            models.Index(fields=["company_id", "created_at"]),
            models.Index(fields=["company_id", "part", "created_at"]),
            models.Index(fields=["company_id", "source_type", "created_at"]),
            models.Index(fields=["company_id", "idempotency_key"]),
        ]

    def _find_idempotent_duplicate_v2(self) -> "StockLedgerEntry | None":
        """
        V2 idempotency guard (preferred):
        company_id + idempotency_scope + idempotency_key  (when key is present)
        """
        if not self._state.adding:
            return None
        if not self.idempotency_key:
            return None

        return (
            StockLedgerEntry.objects.filter(
                company_id=self.company_id,
                idempotency_scope=self.idempotency_scope,
                idempotency_key=self.idempotency_key,
            )
            .only("id", "created_at")
            .first()
        )

    def _find_idempotent_duplicate_v1(self) -> "StockLedgerEntry | None":
        """
        V1 idempotency guard (append-only, logical-key fallback).
        company_id + part + movement_type + source_type + qty + unit_cost + reference_price + source_ref

        DB-level unique index (D-3.11) enforces this under concurrency.
        """
        if not self._state.adding:
            return None

        return (
            StockLedgerEntry.objects.filter(
                company_id=self.company_id,
                part_id=self.part_id,
                movement_type=self.movement_type,
                source_type=self.source_type,
                qty=self.qty,
                unit_cost=self.unit_cost,
                reference_price=self.reference_price,
                source_ref=self.source_ref,
            )
            .only("id", "created_at")
            .first()
        )

    def clean(self):
        super().clean()

        # If idempotency_key is present, scope must also be present (fail-fast)
        if self.idempotency_key and not self.idempotency_scope:
            raise ValidationError("idempotency_scope is required when idempotency_key is provided")

    def save(self, *args, **kwargs):
        # Append-only: update forbidden
        if self.pk and not self._state.adding:
            raise PermissionDenied("StockLedgerEntry is immutable (append-only)")

        # Company boundary safety
        if self.part_id is None:
            raise ValidationError("part is required")
        if self.part.company_id != self.company_id:
            raise ValidationError("company_id mismatch between StockLedgerEntry and Part")

        # Deterministic transaction_value
        if self.unit_cost is None:
            raise ValidationError("unit_cost is required")
        if self.qty is None:
            raise ValidationError("qty is required")

        self.full_clean()
        self.transaction_value = (Decimal(self.qty) * Decimal(self.unit_cost))

        # App-level idempotency guard (fast-path): v2 first, then v1
        dup = self._find_idempotent_duplicate_v2() or self._find_idempotent_duplicate_v1()
        if dup:
            self.id = dup.id
            self.created_at = dup.created_at
            self._state.adding = False
            return None

        is_new = self._state.adding

        # DB-level safety guard (race condition): unique indexes may raise IntegrityError
        try:
            with transaction.atomic():
                result = super().save(*args, **kwargs)
        except IntegrityError:
            dup2 = self._find_idempotent_duplicate_v2() or self._find_idempotent_duplicate_v1()
            if dup2:
                self.id = dup2.id
                self.created_at = dup2.created_at
                self._state.adding = False
                return None
            raise

        # IMPORTANT: local import to avoid circular import at startup
        if is_new:
            from apps.inventory.hooks import on_ledger_insert

            on_ledger_insert(entry=self)

        return result

    def delete(self, *args, **kwargs):
        raise PermissionDenied("StockLedgerEntry delete is forbidden (append-only)")


class PartStockSummary(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    company_id = models.UUIDField()

    part = models.OneToOneField(Part, on_delete=models.CASCADE, related_name="stock_summary")

    available_qty = models.DecimalField(max_digits=18, decimal_places=6, default=Decimal("0"))
    weighted_avg_cost = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("0"))

    last_purchase_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    last_production_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inventory_part_stock_summary"
        constraints = [
            models.UniqueConstraint(fields=["company_id", "part"], name="uq_inventory_stocksummary_company_part"),
        ]
        indexes = [
            models.Index(fields=["company_id", "updated_at"]),
        ]
