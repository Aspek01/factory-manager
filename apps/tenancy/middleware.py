from django.utils.deprecation import MiddlewareMixin

from apps.tenancy.context import set_active_scope
from apps.tenancy.rbac import resolve_membership, apply_membership_scope
from apps.audit.hooks import audit_event


class TenantRBACMiddleware(MiddlewareMixin):
    """
    Resolves UserMembership and enforces role-based scope binding per request.
    """

    def process_request(self, request):
        # Reset scope per request
        set_active_scope(None)

        if not request.user.is_authenticated:
            return
        
       # Django admin should not be gated by tenancy membership
        if request.path.startswith("/admin/"):
            return

        membership = resolve_membership(request.user)
        apply_membership_scope(membership)

        # Determine dynamic scope
        scope = "COMPANY"
        if membership.facility_id:
            scope = "FACILITY"
        if membership.section_id:
            scope = "SECTION"
        if membership.workstation_id:
            scope = "WORKSTATION"

        # Audit: RBAC scope applied (append-only)
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

from django.utils.deprecation import MiddlewareMixin
from apps.tenancy.context import set_active_scope

class TenantContextMiddleware(MiddlewareMixin):
    """
    Minimal context reset middleware.
    Ensures per-request tenancy context is clean before other middleware runs.
    """
    def process_request(self, request):
        set_active_scope(None)
        return None

