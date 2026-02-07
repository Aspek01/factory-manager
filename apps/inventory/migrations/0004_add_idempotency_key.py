from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    # REQUIRED: CREATE INDEX CONCURRENTLY cannot run inside a transaction block
    atomic = False

    dependencies = [
        ("inventory", "0003_dedupe_ledger_then_unique_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockledgerentry",
            name="idempotency_key",
            field=models.CharField(max_length=128, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="stockledgerentry",
            name="idempotency_scope",
            field=models.CharField(
                max_length=16,
                null=True,
                blank=True,
                help_text="SYSTEM|COMPANY|FACILITY|SECTION|WORKSTATION (nullable).",
            ),
        ),
        migrations.RunSQL(
            sql="""
                CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ux_inventory_stock_ledger_idempotency_v2
                ON inventory_stock_ledger (company_id, idempotency_scope, idempotency_key)
                WHERE idempotency_key IS NOT NULL;
            """,
            reverse_sql="""
                DROP INDEX CONCURRENTLY IF EXISTS ux_inventory_stock_ledger_idempotency_v2;
            """,
        ),
    ]
