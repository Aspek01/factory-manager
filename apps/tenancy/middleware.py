from django.utils.deprecation import MiddlewareMixin

from apps.audit.hooks import audit_event
from apps.tenancy.context import set_active_scope
from apps.tenancy.rbac import resolve_membership, apply_membership_scope


class TenantContextMiddleware(MiddlewareMixin):
    """
    Hard reset of tenancy context per request.
    Deterministic isolation guard.
    """

    def process_request(self, request):
        set_active_scope(None)
        return None


class TenantRBACMiddleware(MiddlewareMixin):
    """
    Resolves UserMembership and enforces role-based scope binding per request.
    """

    def process_request(self, request):
        # Defensive reset (idempotent)
        set_active_scope(None)

        if not request.user.is_authenticated:
            return

        # Django admin must bypass tenancy gating
        if request.path.startswith("/admin/"):
            return

        membership = resolve_membership(request.user)
        apply_membership_scope(membership)

        # Dynamic scope resolution (LOCKED hierarchy)
        scope = "COMPANY"
        if membership.facility_id:
            scope = "FACILITY"
        if membership.section_id:
            scope = "SECTION"
        if membership.workstation_id:
            scope = "WORKSTATION"

        # Append-only audit
        audit_event(
            company_id=membership.company_id,
            actor_user_id=membership.user_id,
            event_type="rbac.scope.applied",
            scope=scope,
            payload={
                "role": membership.role,
                "facility_id": membership.facility_id,
                "section_id": membership.section_id,
                "workstation_id": membership.workstation_id,
            },
        )
