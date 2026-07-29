"""Experience controller — public read, admin write."""

from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, PermissionAPIError
from django_matt.core.router import delete, get, patch, post

from {{ project_name }}_app.experience.models import Experience
from {{ project_name }}_app.experience.schemas import (
    ExperienceCreateSchema,
    ExperienceSchema,
    ExperienceUpdateSchema,
)


class ExperienceController(APIController):
    prefix = "/experience"
    tags = ["Experience"]

    @get("/")
    async def list_experience(self) -> list[ExperienceSchema]:
        return [ExperienceSchema.model_validate(e) async for e in Experience.objects.all()]

    @post("/")
    @jwt_required
    async def create_experience(
        self, request, body: ExperienceCreateSchema
    ) -> ExperienceSchema:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can create experience entries.")
        exp = await Experience.objects.acreate(**body.model_dump())
        return ExperienceSchema.model_validate(exp)

    @patch("/{exp_id}")
    @jwt_required
    async def update_experience(
        self, request, exp_id: str, body: ExperienceUpdateSchema
    ) -> ExperienceSchema:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can update experience.")
        exp = await Experience.objects.filter(id=exp_id).afirst()
        if exp is None:
            raise NotFoundAPIError("Experience entry not found.")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(exp, field, value)
        await exp.asave()
        return ExperienceSchema.model_validate(exp)

    @delete("/{exp_id}")
    @jwt_required
    async def delete_experience(self, request, exp_id: str) -> dict:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can delete experience.")
        deleted, _ = await Experience.objects.filter(id=exp_id).adelete()
        if not deleted:
            raise NotFoundAPIError("Experience entry not found.")
        return {"deleted": True}
