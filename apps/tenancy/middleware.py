from django.http import JsonResponse
from apps.tenancy.context import set_active_scope


class TenantContextMiddleware:
    """
    LOCKED: active_company_id required on every request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        company_id = request.headers.get("X-Company-ID")
        if not company_id:
            return JsonResponse({"detail": "active_company_id is required"}, status=403)

        set_active_scope(company_id=company_id)
        return self.get_response(request)
