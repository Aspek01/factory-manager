from __future__ import annotations

import os
from uuid import UUID

from django.core.management.base import BaseCommand

from apps.audit.hooks import emit_audit_event


class _SeedContext:
    """
    Minimal, deterministic context for audit guards.
    Only requirement: company_id attribute.
    """
    def __init__(self, company_id):
        self.company_id = company_id


class Command(BaseCommand):
    help = (
        "Emit a minimal audit event to verify append-only audit pipeline.\n"
        "Requires environment variable: SEED_COMPANY_ID (UUID)."
    )

    def handle(self, *args, **options):
        raw = (os.environ.get("SEED_COMPANY_ID") or "").strip()
        if not raw:
            raise RuntimeError(
                "SEED_COMPANY_ID environment variable is required.\n"
                "PowerShell example:\n"
                "$env:SEED_COMPANY_ID='00000000-0000-0000-0000-000000000000'"
            )

        try:
            company_id = UUID(raw)
        except Exception as exc:
            raise RuntimeError(
                f"Invalid SEED_COMPANY_ID (must be UUID): {raw}"
            ) from exc

        ctx = _SeedContext(company_id=company_id)

        emit_audit_event(
            event_name="system.seed.executed",
            payload={"by": "audit_seed"},
            context=ctx,
            actor_id=None,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "audit_seed OK — system.seed.executed emitted (append-only)"
            )
        )
