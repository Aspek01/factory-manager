from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


PATTERNS = [
    re.compile(r"\bAuditEvent\.objects\.create\s*\("),
    re.compile(r"\bAuditEvent\.objects\.bulk_create\s*\("),
]

# Allowed direct writes (the official entrypoint)
ALLOWLIST = {
    "apps/audit/hooks.py",
}


class Command(BaseCommand):
    help = "Fail-fast scan for forbidden direct AuditEvent writes. Use emit_audit_event() instead."

    def handle(self, *args, **options):
        base = Path(settings.BASE_DIR)

        exclude_parts = {"venv", ".venv", ".git", "node_modules", "__pycache__", "migrations"}

        hits = []
        for path in base.rglob("*.py"):
            if any(part in exclude_parts for part in path.parts):
                continue

            rel = path.relative_to(base).as_posix()
            if rel in ALLOWLIST:
                continue

            text = path.read_text(encoding="utf-8", errors="ignore")
            for rx in PATTERNS:
                if rx.search(text):
                    hits.append(rel)
                    break

        if hits:
            msg = "Forbidden direct audit writes detected:\n" + "\n".join(f"- {p}" for p in sorted(set(hits)))
            raise CommandError(msg)

        self.stdout.write(self.style.SUCCESS("audit_scan OK — no forbidden direct writes found"))
