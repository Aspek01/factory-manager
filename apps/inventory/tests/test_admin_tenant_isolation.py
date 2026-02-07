from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.inventory.models import Part, PartStockSummary, StockLedgerEntry


class AdminTenantIsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.superuser = User.objects.create_superuser(
            username="su",
            email="su@example.com",
            password="pass12345",
        )

        cls.staff = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            password="pass12345",
            is_staff=True,
            is_active=True,
        )

        perms = Permission.objects.filter(
            codename__in=[
                "view_stockledgerentry",
                "view_partstocksummary",
                "view_part",
                "view_bom",
                "view_bomitem",
            ]
        )
        cls.staff.user_permissions.add(*perms)

        cls.company_a = UUID("11111111-1111-1111-1111-111111111111")
        cls.company_b = UUID("22222222-2222-2222-2222-222222222222")

        cls.part_a = Part.objects.create(
            company_id=cls.company_a,
            part_no="A-001",
            name="Part A",
            part_type=Part.PartType.RAW_MATERIAL,
            procurement_strategy=Part.ProcurementStrategy.BUY,
        )
        cls.part_b = Part.objects.create(
            company_id=cls.company_b,
            part_no="B-001",
            name="Part B",
            part_type=Part.PartType.RAW_MATERIAL,
            procurement_strategy=Part.ProcurementStrategy.BUY,
        )

        cls.ledger_a = StockLedgerEntry.objects.create(
            company_id=cls.company_a,
            part=cls.part_a,
            movement_type=StockLedgerEntry.MovementType.IN,
            source_type=StockLedgerEntry.SourceType.PURCHASE,
            qty=Decimal("10.000000"),
            unit_cost=Decimal("5.0000"),
            transaction_value=Decimal("0.0000"),
            reference_price=None,
            source_ref={"doc": "GR-1"},
        )
        cls.ledger_b = StockLedgerEntry.objects.create(
            company_id=cls.company_b,
            part=cls.part_b,
            movement_type=StockLedgerEntry.MovementType.IN,
            source_type=StockLedgerEntry.SourceType.PURCHASE,
            qty=Decimal("7.000000"),
            unit_cost=Decimal("3.0000"),
            transaction_value=Decimal("0.0000"),
            reference_price=None,
            source_ref={"doc": "GR-2"},
        )

        cls.summary_a, _ = PartStockSummary.objects.get_or_create(
            part=cls.part_a,
            defaults={
                "company_id": cls.company_a,
                "available_qty": Decimal("10.000000"),
                "weighted_avg_cost": Decimal("5.0000"),
            },
        )
        cls.summary_b, _ = PartStockSummary.objects.get_or_create(
            part=cls.part_b,
            defaults={
                "company_id": cls.company_b,
                "available_qty": Decimal("7.000000"),
                "weighted_avg_cost": Decimal("3.0000"),
            },
        )

    def test_superuser_can_see_all_ledgers(self):
        self.client.force_login(self.superuser)

        url = reverse("admin:inventory_stockledgerentry_changelist")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        cl = resp.context["cl"]
        self.assertEqual(cl.result_count, 2)

    def test_superuser_can_see_all_summaries(self):
        self.client.force_login(self.superuser)

        url = reverse("admin:inventory_partstocksummary_changelist")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        cl = resp.context["cl"]
        self.assertEqual(cl.result_count, 2)

    def test_non_system_without_tenant_scope_sees_nothing_fail_closed(self):
        self.client.force_login(self.staff)

        url1 = reverse("admin:inventory_stockledgerentry_changelist")
        r1 = self.client.get(url1)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.context["cl"].result_count, 0)

        url2 = reverse("admin:inventory_partstocksummary_changelist")
        r2 = self.client.get(url2)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.context["cl"].result_count, 0)

    def test_non_system_detail_view_denied_or_not_found_out_of_scope(self):
        """
        For unresolved tenant scope, detail access must not reveal the object.

        Django admin may:
        - return 403 (PermissionDenied), OR
        - return 404 (not found), OR
        - redirect (302) to changelist with a message when object isn't in queryset.

        IMPORTANT: 302 must NOT be a redirect to /admin/login/.
        """
        self.client.force_login(self.staff)

        ledger_url = reverse("admin:inventory_stockledgerentry_change", args=[str(self.ledger_a.id)])
        r = self.client.get(ledger_url, follow=False)

        if r.status_code == 302:
            loc = r.headers.get("Location", "") or ""

            # must not be auth redirect
            self.assertNotIn("/admin/login/", loc)

            # admin may redirect either to app index (/admin/) or model changelist
            self.assertTrue(
                loc.startswith("/admin/"),
                f"Unexpected redirect location: {loc}",
            )
            return


        self.assertIn(r.status_code, (403, 404))
