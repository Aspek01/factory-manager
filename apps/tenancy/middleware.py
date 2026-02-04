from django.utils.deprecation import MiddlewareMixin

from apps.tenancy.context import set_active_scope
from apps.tenancy.rbac import resolve_membership, apply_membership_scope


class TenantRBACMiddleware(MiddlewareMixin):
    """
    Resolves UserMembership and enforces role-based scope binding per request.
    """

    def process_request(self, request):
        # Reset scope per request
        set_active_scope(None)

        if not request.user.is_authenticated:
            return

        membership = resolve_membership(request.user)
        apply_membership_scope(membership)
