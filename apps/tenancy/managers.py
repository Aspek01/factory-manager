from __future__ import annotations

from django.db import models

from apps.tenancy.context import require_active_company_id


class TenantQuerySet(models.QuerySet):
    """
    Automatically scopes queries by active_company_id for company-bound models.
    """

    def _with_tenant(self):
        company_id = require_active_company_id()
        return self.filter(company_id=company_id)

    def all(self):
        return self._with_tenant()

    def filter(self, *args, **kwargs):
        qs = super().filter(*args, **kwargs)
        # If caller already provided company/company_id, do not override.
        if "company" in kwargs or "company_id" in kwargs:
            return qs
        return qs._with_tenant()

    def exclude(self, *args, **kwargs):
        qs = super().exclude(*args, **kwargs)
        if "company" in kwargs or "company_id" in kwargs:
            return qs
        return qs._with_tenant()


class TenantManager(models.Manager):
    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)
