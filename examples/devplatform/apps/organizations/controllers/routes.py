from django_matt import DjangoMattAPI

from apps.organizations.schemas import (
    MembershipSchema,
    OrganizationSchema,
    OrganizationWithRoleSchema,
)

from .member_controller import MemberController
from .organization_controller import OrganizationController


def register_org_routes(api: DjangoMattAPI) -> None:
    # Organizations
    api.get(
        "organizations",
        response_model=list[OrganizationWithRoleSchema],
        tags=["Organizations"],
    )(OrganizationController.list_organizations)

    api.post(
        "organizations",
        response_model=OrganizationSchema,
        status_code=201,
        tags=["Organizations"],
    )(OrganizationController.create_organization)

    api.get(
        "organizations/<str:org_id>",
        response_model=OrganizationSchema,
        tags=["Organizations"],
    )(OrganizationController.get_organization)

    api.patch(
        "organizations/<str:org_id>",
        response_model=OrganizationSchema,
        tags=["Organizations"],
    )(OrganizationController.update_organization)

    api.delete(
        "organizations/<str:org_id>",
        tags=["Organizations"],
    )(OrganizationController.delete_organization)

    # Members
    api.get(
        "organizations/<str:org_id>/members",
        response_model=list[MembershipSchema],
        tags=["Members"],
    )(MemberController.list_members)

    api.patch(
        "organizations/<str:org_id>/members/<str:member_id>",
        response_model=MembershipSchema,
        tags=["Members"],
    )(MemberController.update_member)

    api.delete(
        "organizations/<str:org_id>/members/<str:member_id>",
        tags=["Members"],
    )(MemberController.remove_member)
