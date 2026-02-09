from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, models, transaction
from django.db.models import Case, DecimalField, Sum, Value, When
from django.db.models.functions import Coalesce

from apps.audit.hooks import emit_audit_event
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

    # D-3.27 — Reverse schema (correction via reverse entry; still append-only)
    reverse_of = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversed_by",
        help_text="If set, this row is the reverse/correction entry of the referenced original row.",
    )

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

    def _movement_delta_qty(self) -> Decimal:
        q = Decimal(self.qty)
        if self.movement_type == self.MovementType.IN:
            return q
        if self.movement_type == self.MovementType.OUT:
            return -q
        return q  # adjustment is signed

    def _acquire_part_xact_lock(self) -> None:
        if connection.vendor == "postgresql":
            key = (int(self.company_id) ^ int(self.part_id)) & 0x7FFFFFFFFFFFFFFF
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s);", [key])
            return

        Part.objects.select_for_update().only("id").get(id=self.part_id)

    def _current_available_qty_locked(self) -> Decimal:
        signed = Case(
            When(movement_type=self.MovementType.IN, then=models.F("qty")),
            When(movement_type=self.MovementType.OUT, then=models.F("qty") * Value(Decimal("-1"))),
            When(movement_type=self.MovementType.ADJUSTMENT, then=models.F("qty")),
            default=Value(Decimal("0")),
            output_field=DecimalField(max_digits=18, decimal_places=6),
        )
        agg = (
            StockLedgerEntry.objects.filter(company_id=self.company_id, part_id=self.part_id)
            .aggregate(total=Coalesce(Sum(signed), Value(Decimal("0"))))
        )
        return Decimal(agg["total"])

    def _emit_negative_stock_block_audit(self, *, current: Decimal, delta: Decimal, projected: Decimal) -> None:
        """
        Emit audit OUTSIDE the ledger insert transaction (so it persists even when we block).
        Best-effort: audit failure must not mask the original ValidationError.
        """

        class _Ctx:
            def __init__(self, company_id):
                self.company_id = company_id
                self.is_system = False

        ctx = _Ctx(self.company_id)

        try:
            emit_audit_event(
                event_name="inventory.negative_stock.blocked",
                payload={
                    "part_id": str(self.part_id),
                    "movement_type": str(self.movement_type),
                    "source_type": str(self.source_type),
                    "qty": str(self.qty),
                    "delta_qty": str(delta),
                    "current_available_qty": str(current),
                    "projected_available_qty": str(projected),
                    "unit_cost": str(self.unit_cost),
                    "reference_price": str(self.reference_price) if self.reference_price is not None else None,
                    "source_ref": self.source_ref or {},
                    "idempotency_key": self.idempotency_key,
                    "idempotency_scope": self.idempotency_scope,
                },
                context=ctx,
                actor_id=None,
            )
        except Exception:
            return

    def clean(self):
        super().clean()

        if self.idempotency_key and not self.idempotency_scope:
            raise ValidationError("idempotency_scope is required when idempotency_key is provided")

        # D-3.27 — Reverse semantics (fail-fast)
        if self.reverse_of_id:
            if self.reverse_of_id == self.id:
                raise ValidationError("reverse_of cannot point to itself")

            orig = self.reverse_of  # resolved by Django (FK cache)
            if orig.company_id != self.company_id:
                raise ValidationError("company_id mismatch between reverse entry and original entry")

            # single-step: do not allow reversing a reverse entry
            if getattr(orig, "reverse_of_id", None):
                raise ValidationError("cannot reverse a reverse entry")

            # reverse rows must be adjustment source (traceable correction lane)
            if self.source_type != self.SourceType.ADJUSTMENT:
                raise ValidationError("reverse entries must use source_type=adjustment")

            # movement rule
            if orig.movement_type == self.MovementType.IN:
                if self.movement_type != self.MovementType.OUT:
                    raise ValidationError("reverse of an IN must be an OUT")
                if Decimal(self.qty) != Decimal(orig.qty):
                    raise ValidationError("reverse qty must match original qty for IN/OUT")
            elif orig.movement_type == self.MovementType.OUT:
                if self.movement_type != self.MovementType.IN:
                    raise ValidationError("reverse of an OUT must be an IN")
                if Decimal(self.qty) != Decimal(orig.qty):
                    raise ValidationError("reverse qty must match original qty for IN/OUT")
            else:
                # adjustment reversed by adjustment with -qty
                if self.movement_type != self.MovementType.ADJUSTMENT:
                    raise ValidationError("reverse of an ADJUSTMENT must be an ADJUSTMENT")
                if Decimal(self.qty) != (Decimal(orig.qty) * Decimal("-1")):
                    raise ValidationError("reverse qty must be -original.qty for ADJUSTMENT")

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise PermissionDenied("StockLedgerEntry is immutable (append-only)")

        if self.part_id is None:
            raise ValidationError("part is required")
        if self.part.company_id != self.company_id:
            raise ValidationError("company_id mismatch between StockLedgerEntry and Part")

        if self.unit_cost is None:
            raise ValidationError("unit_cost is required")
        if self.qty is None:
            raise ValidationError("qty is required")

        self.full_clean()

        qty_dec = Decimal(self.qty)
        if self.movement_type in {self.MovementType.IN, self.MovementType.OUT} and qty_dec <= 0:
            raise ValidationError("qty must be > 0 for movement_type in/out")
        if self.movement_type == self.MovementType.ADJUSTMENT and qty_dec == 0:
            raise ValidationError("qty must be non-zero for movement_type adjustment")

        self.transaction_value = (Decimal(self.qty) * Decimal(self.unit_cost))

        dup = self._find_idempotent_duplicate_v2() or self._find_idempotent_duplicate_v1()
        if dup:
            self.id = dup.id
            self.created_at = dup.created_at
            self._state.adding = False
            return None

        is_new = self._state.adding

        try:
            with transaction.atomic():
                delta = self._movement_delta_qty()

                # D-3.25 — Negative stock guard:
                # reverse/correction entries are an explicit exception lane (spec) -> do not block.
                if delta < 0 and not self.reverse_of_id:
                    self._acquire_part_xact_lock()
                    current = self._current_available_qty_locked()
                    projected = current + delta
                    if projected < 0:
                        raise ValidationError("negative stock not allowed (ledger-time guard)")

                result = super().save(*args, **kwargs)

        except ValidationError as exc:
            if "negative stock not allowed (ledger-time guard)" in str(exc):
                try:
                    delta = self._movement_delta_qty()
                    current = self._current_available_qty_locked()
                    projected = current + delta
                except Exception:
                    delta = self._movement_delta_qty()
                    current = Decimal("0")
                    projected = Decimal("0")

                self._emit_negative_stock_block_audit(current=current, delta=delta, projected=projected)
            raise

        except IntegrityError:
            dup2 = self._find_idempotent_duplicate_v2() or self._find_idempotent_duplicate_v1()
            if dup2:
                self.id = dup2.id
                self.created_at = dup2.created_at
                self._state.adding = False
                return None
            raise

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
