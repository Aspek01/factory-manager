from __future__ import annotations

from contextvars import ContextVar


# Only emit_audit_event() may set this to True during write.
AUDIT_EMIT_ALLOWED: ContextVar[bool] = ContextVar("AUDIT_EMIT_ALLOWED", default=False)
