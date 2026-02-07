from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    """
    D-3.11
    DB-level unique index for StockLedgerEntry logical key to prevent duplicates under concurrency.

    Logical key (MVP):
      company_id, part_id, movement_type, source_type, qty, unit_cost, reference_price(nullable), source_ref(jsonb)

    NOTE:
    - reference_price is nullable; Postgres UNIQUE treats NULLs as distinct.
      For idempotency we want NULL == NULL, so we index on COALESCE(reference_price, -1.0000).
      Negative price is invalid in MVP, safe sentinel.
    """

    dependencies = [
        ("inventory", "0001_initial"),
    ]

    # Required for CREATE INDEX CONCURRENTLY
    atomic = False

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ux_inventory_stock_ledger_logical_key
            ON inventory_stock_ledger (
                company_id,
                part_id,
                movement_type,
                source_type,
                qty,
                unit_cost,
                (COALESCE(reference_price, -1.0000)),
                source_ref
            );
            """,
            reverse_sql="""
            DROP INDEX CONCURRENTLY IF EXISTS ux_inventory_stock_ledger_logical_key;
            """,
        ),
    ]
