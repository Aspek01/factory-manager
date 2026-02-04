from __future__ import annotations

import uuid
from django.core.exceptions import ValidationError
from django.db import models


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
