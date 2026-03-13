import uuid
from enum import Enum

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class MembershipRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class Membership(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=[(r.value, r.value) for r in MembershipRole],
        default=MembershipRole.MEMBER.value,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "memberships"
        unique_together = [("user", "organization")]

    def __str__(self) -> str:
        return f"{self.user} - {self.organization} ({self.role})"

    @property
    def is_admin(self) -> bool:
        return self.role in (MembershipRole.OWNER.value, MembershipRole.ADMIN.value)

    @property
    def is_owner(self) -> bool:
        return self.role == MembershipRole.OWNER.value
