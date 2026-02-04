from __future__ import annotations

import uuid
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings


# ─────────────────────────────────────────────────────────────
# TENANCY CORE
# ─────────────────────────────────────────────────────────────

class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "companies"

    def __str__(self) -> str:
        return self.name


class Facility(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="facilities")
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "facilities"
        unique_together = [("company", "name")]

    def clean(self):
        if not self.company_id:
            raise ValidationError("Facility.company is required")

    def __str__(self) -> str:
        return f"{self.company.name} / {self.name}"


class Section(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # denormalized, LOCKED
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="sections")
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="sections")

    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sections"
        unique_together = [("facility", "name")]

    def clean(self):
        if self.facility.company_id != self.company_id:
            raise ValidationError("Section.company must match Facility.company")

    def __str__(self) -> str:
        return f"{self.facility} / {self.name}"


class Workstation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # denormalized, LOCKED
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="workstations")
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="workstations")

    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "workstations"
        unique_together = [("company", "code")]

    def clean(self):
        if self.section.company_id != self.company_id:
            raise ValidationError("Workstation.company must match Section.company")

    def __str__(self) -> str:
        return f"{self.section} / {self.code}"


# ─────────────────────────────────────────────────────────────
# RBAC / MEMBERSHIP (D-1.1 — LOCKED)
# ─────────────────────────────────────────────────────────────

class Role(models.TextChoices):
    SYSTEM_ADMIN = "system_admin", "system_admin"
    COMPANY_MANAGER = "company_manager", "company_manager"
    SALES_ENGINEER = "sales_engineer", "sales_engineer"
    PRODUCTION_ENGINEER = "production_engineer", "production_engineer"
    PLANNER = "planner", "planner"
    PURCHASING = "purchasing", "purchasing"
    GOODS_RECEIPT_CLERK = "goods_receipt_clerk", "goods_receipt_clerk"
    SECTION_SUPERVISOR = "section_supervisor", "section_supervisor"
    QUALITY_INSPECTOR = "quality_inspector", "quality_inspector"
    OPERATOR = "operator", "operator"


class UserMembership(models.Model):
    """
    LOCKED RULES:
    - system_admin hariç her user tam 1 company'ye bağlıdır
    - role → primary scope binding DB seviyesinde tutulur
    - cross-company binding kesin yasak
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membership",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    role = models.CharField(
        max_length=64,
        choices=Role.choices,
    )

    # Primary scope bindings (role’e göre zorunlu / yasak)
    facility = models.ForeignKey(
        Facility,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="memberships",
    )

    section = models.ForeignKey(
        Section,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="memberships",
    )

    workstation = models.ForeignKey(
        Workstation,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="memberships",
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_memberships"

    def clean(self):
        # ── Company consistency (HARD)
        if self.facility and self.facility.company_id != self.company_id:
            raise ValidationError("Membership.company must match Facility.company")

        if self.section and self.section.company_id != self.company_id:
            raise ValidationError("Membership.company must match Section.company")

        if self.workstation and self.workstation.company_id != self.company_id:
            raise ValidationError("Membership.company must match Workstation.company")

        # ── Role-based scope binding rules (LOCKED)
        if self.role == Role.SYSTEM_ADMIN:
            if self.facility or self.section or self.workstation:
                raise ValidationError("system_admin cannot bind facility/section/workstation")
            return

        if self.role in {Role.COMPANY_MANAGER, Role.SALES_ENGINEER}:
            if self.facility or self.section or self.workstation:
                raise ValidationError("company-scope roles cannot bind facility/section/workstation")
            return

        if self.role in {
            Role.PRODUCTION_ENGINEER,
            Role.PLANNER,
            Role.PURCHASING,
            Role.GOODS_RECEIPT_CLERK,
            Role.QUALITY_INSPECTOR,
        }:
            if not self.facility or self.section or self.workstation:
                raise ValidationError("facility-scope roles must bind facility only")
            return

        if self.role == Role.SECTION_SUPERVISOR:
            if not self.section or self.facility or self.workstation:
                raise ValidationError("section_supervisor must bind section only")
            return

        if self.role == Role.OPERATOR:
            if not self.workstation or self.facility or self.section:
                raise ValidationError("operator must bind workstation only")
            return
from apps.tenancy.managers import TenantManager


class CompanyBoundModel(models.Model):
    """
    Abstract base for all tenant-bound domain models.
    Enforces automatic ORM scoping via TenantManager.
    """

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="+")

    objects = TenantManager()

    class Meta:
        abstract = True
