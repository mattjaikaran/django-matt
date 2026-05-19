from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError

from apps.skills.models import Skill
from apps.skills.schemas import SkillCreateSchema, SkillSchema, SkillUpdateSchema


def _serialize(skill: Skill) -> dict:
    return SkillSchema(
        id=str(skill.id),
        name=skill.name,
        category=skill.category,
        level=skill.level,
        icon=skill.icon,
        order=skill.order,
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    ).model_dump(mode="json")


class SkillController(APIController):
    tags = ["Skills"]

    @staticmethod
    async def list_skills(request) -> dict:
        params = request.GET
        qs = Skill.objects.all()

        if category := params.get("category"):
            qs = qs.filter(category=category)

        items = []
        async for skill in qs:
            items.append(_serialize(skill))

        return {"items": items, "total": len(items)}

    @staticmethod
    @jwt_required
    async def create_skill(request, body: SkillCreateSchema) -> dict:
        skill = await Skill.objects.acreate(
            name=body.name,
            category=body.category,
            level=body.level,
            icon=body.icon,
            order=body.order,
        )
        return _serialize(skill)

    @staticmethod
    async def get_skill(request, skill_id: str) -> dict:
        skill = await Skill.objects.filter(id=skill_id).afirst()
        if not skill:
            raise NotFoundAPIError("Skill not found")
        return _serialize(skill)

    @staticmethod
    @jwt_required
    async def update_skill(request, skill_id: str, body: SkillUpdateSchema) -> dict:
        skill = await Skill.objects.filter(id=skill_id).afirst()
        if not skill:
            raise NotFoundAPIError("Skill not found")

        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(skill, field, value)
        await skill.asave()
        return _serialize(skill)

    @staticmethod
    @jwt_required
    async def delete_skill(request, skill_id: str) -> dict:
        skill = await Skill.objects.filter(id=skill_id).afirst()
        if not skill:
            raise NotFoundAPIError("Skill not found")
        await skill.adelete()
        return {"message": "Skill deleted"}
