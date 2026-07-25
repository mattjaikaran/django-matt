"""
Pydantic schemas for multi-tenant resources.
"""


from django_matt.core.schema import ModelSchema

from tenants.models import Membership, Organization, Project


class OrganizationSchema(ModelSchema):
    member_count: int = 0

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "plan", "created_at"]


class CreateOrganizationInput(ModelSchema):
    class Meta:
        model = Organization
        fields = ["name", "slug", "plan"]
        fields_optional = ["plan"]


class MembershipSchema(ModelSchema):
    class Meta:
        model = Membership
        fields = ["id", "user_id", "role", "joined_at"]


class ProjectSchema(ModelSchema):
    class Meta:
        model = Project
        fields = ["id", "name", "description", "is_archived", "created_at", "updated_at"]


class CreateProjectInput(ModelSchema):
    class Meta:
        model = Project
        fields = ["name", "description"]
        fields_optional = ["description"]
