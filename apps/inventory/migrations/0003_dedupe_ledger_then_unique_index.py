from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    """
    D-3.11-FIX
    - Deduplicate existing rows that violate the ledger logical key (MVP).
    - Then create the DB-level unique index for concurrency safety.

    Why:
    - Postgres UNIQUE treats NULLs as distinct. We want NULL == NULL for reference_price,
      so we index on COALESCE(reference_price, -1.0000) as sentinel.
    - Existing duplicate rows can exist from earlier dev runs (pre D-3.9 guard),
      which blocks index creation. We keep the earliest row and delete the rest.

    Deterministic keep policy:
    - Keep the earliest by (created_at ASC, id ASC); delete rows with rn > 1.
    """

    dependencies = [
        ("inventory", "0002_ledger_logical_key_unique"),
    ]

    atomic = False

    operations = [
        migrations.RunSQL(
            sql="""
            -- 1) Dedupe (keep earliest row per logical key)
            WITH ranked AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY
                            company_id,
                            part_id,
                            movement_type,
                            source_type,
                            qty,
                            unit_cost,
                            COALESCE(reference_price, -1.0000),
                            source_ref
                        ORDER BY created_at ASC, id ASC
                    ) AS rn
                FROM inventory_stock_ledger
            )
            DELETE FROM inventory_stock_ledger
            WHERE id IN (SELECT id FROM ranked WHERE rn > 1);

            -- 2) Create unique index (non-concurrently here because we're in a controlled dev flow)
            --    If you want CONCURRENTLY later, we can introduce it in a prod-safe migration.
            CREATE UNIQUE INDEX IF NOT EXISTS ux_inventory_stock_ledger_logical_key
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
            DROP INDEX IF EXISTS ux_inventory_stock_ledger_logical_key;
            """,
        ),
    ]
