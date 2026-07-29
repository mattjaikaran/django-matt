"""Skill controller — public read, admin write."""

from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, PermissionAPIError
from django_matt.core.router import delete, get, patch, post

from {{ project_name }}_app.skills.models import Skill
from {{ project_name }}_app.skills.schemas import SkillCreateSchema, SkillSchema, SkillUpdateSchema


class SkillController(APIController):
    prefix = "/skills"
    tags = ["Skills"]

    @get("/")
    async def list_skills(self, category: str | None = None) -> list[SkillSchema]:
        qs = Skill.objects.order_by("category", "order", "name")
        if category:
            qs = qs.filter(category=category)
        return [SkillSchema.model_validate(s) async for s in qs]

    @post("/")
    @jwt_required
    async def create_skill(self, request, body: SkillCreateSchema) -> SkillSchema:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can create skills.")
        skill = await Skill.objects.acreate(**body.model_dump())
        return SkillSchema.model_validate(skill)

    @patch("/{skill_id}")
    @jwt_required
    async def update_skill(
        self, request, skill_id: str, body: SkillUpdateSchema
    ) -> SkillSchema:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can update skills.")
        skill = await Skill.objects.filter(id=skill_id).afirst()
        if skill is None:
            raise NotFoundAPIError("Skill not found.")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(skill, field, value)
        await skill.asave()
        return SkillSchema.model_validate(skill)

    @delete("/{skill_id}")
    @jwt_required
    async def delete_skill(self, request, skill_id: str) -> dict:
        if not request.user.is_staff:
            raise PermissionAPIError("Only staff can delete skills.")
        deleted, _ = await Skill.objects.filter(id=skill_id).adelete()
        if not deleted:
            raise NotFoundAPIError("Skill not found.")
        return {"deleted": True}
