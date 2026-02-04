from __future__ import annotations

from django.core.exceptions import PermissionDenied

from apps.tenancy.context import set_active_scope
from apps.tenancy.models import Role, UserMembership


def resolve_membership(user):
    if not user.is_authenticated:
        raise PermissionDenied("Authentication required")

    try:
        membership = user.membership
    except UserMembership.DoesNotExist:
        raise PermissionDenied("User has no membership")

    if not membership.is_active:
        raise PermissionDenied("Inactive membership")

    return membership


def apply_membership_scope(membership: UserMembership):
    """
    Sets active scope ContextVars based on membership role.
    """
    role = membership.role

    if role == Role.SYSTEM_ADMIN:
        # SYSTEM scope (company context still set for consistency)
        set_active_scope(company_id=membership.company_id)
        return

    if role in {Role.COMPANY_MANAGER, Role.SALES_ENGINEER}:
        set_active_scope(company_id=membership.company_id)
        return

    if role in {
        Role.PRODUCTION_ENGINEER,
        Role.PLANNER,
        Role.PURCHASING,
        Role.GOODS_RECEIPT_CLERK,
        Role.QUALITY_INSPECTOR,
    }:
        set_active_scope(
            company_id=membership.company_id,
            facility_id=membership.facility_id,
        )
        return

    if role == Role.SECTION_SUPERVISOR:
        set_active_scope(
            company_id=membership.company_id,
            section_id=membership.section_id,
        )
        return

    if role == Role.OPERATOR:
        set_active_scope(
            company_id=membership.company_id,
            workstation_id=membership.workstation_id,
        )
        return

    raise PermissionDenied("Unsupported role")
