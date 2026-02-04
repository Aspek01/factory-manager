from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.audit.models import AuditEvent
from apps.tenancy.models import Company, Facility, Section, Workstation, Role, UserMembership
from apps.audit.hooks import audit_event


class Command(BaseCommand):
    help = "Seeds minimal tenancy + membership and emits a sample audit event for verification."

    def handle(self, *args, **options):
        User = get_user_model()

        company, _ = Company.objects.get_or_create(name="Demo Company")
        facility, _ = Facility.objects.get_or_create(company=company, name="Main Facility")
        section, _ = Section.objects.get_or_create(company=company, facility=facility, name="Section A")
        ws, _ = Workstation.objects.get_or_create(company=company, section=section, code="WS-01", defaults={"name": "Workstation 01"})

        user, _ = User.objects.get_or_create(username="demo_cm", defaults={"email": "demo@example.com"})
        user.set_password("demo12345")
        user.save()

        membership, _ = UserMembership.objects.get_or_create(
            user=user,
            defaults={
                "company": company,
                "role": Role.COMPANY_MANAGER,
            },
        )

        scope = "COMPANY"
        audit_event(
            company_id=membership.company_id,
            actor_user_id=membership.user_id,
            event_type="rbac.scope.applied",
            scope=scope,
            payload={"role": membership.role},
        )

        count = AuditEvent.objects.filter(company_id=company.id, event_type="rbac.scope.applied").count()
        self.stdout.write(self.style.SUCCESS(f"OK: emitted rbac.scope.applied. total={count}"))
        self.stdout.write(self.style.SUCCESS("Login: demo_cm / demo12345 (admin panel for viewing events)"))
