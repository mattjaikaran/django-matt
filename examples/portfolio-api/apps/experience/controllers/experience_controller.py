from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError

from apps.experience.models import Experience
from apps.experience.schemas import ExperienceCreateSchema, ExperienceSchema, ExperienceUpdateSchema


def _serialize(exp: Experience) -> dict:
    return ExperienceSchema(
        id=str(exp.id),
        company=exp.company,
        role=exp.role,
        company_url=exp.company_url,
        location=exp.location,
        start_date=exp.start_date,
        end_date=exp.end_date,
        is_current=exp.is_current,
        description=exp.description,
        tech_used=exp.tech_used,
        order=exp.order,
        created_at=exp.created_at,
        updated_at=exp.updated_at,
    ).model_dump(mode="json")


class ExperienceController(APIController):
    tags = ["Experience"]

    @staticmethod
    async def list_experience(request) -> dict:
        items = []
        async for exp in Experience.objects.all():
            items.append(_serialize(exp))
        return {"items": items, "total": len(items)}

    @staticmethod
    @jwt_required
    async def create_experience(request, body: ExperienceCreateSchema) -> dict:
        exp = await Experience.objects.acreate(
            company=body.company,
            role=body.role,
            company_url=body.company_url,
            location=body.location,
            start_date=body.start_date,
            end_date=body.end_date,
            is_current=body.is_current,
            description=body.description,
            tech_used=body.tech_used,
            order=body.order,
        )
        return _serialize(exp)

    @staticmethod
    async def get_experience(request, exp_id: str) -> dict:
        exp = await Experience.objects.filter(id=exp_id).afirst()
        if not exp:
            raise NotFoundAPIError("Experience not found")
        return _serialize(exp)

    @staticmethod
    @jwt_required
    async def update_experience(request, exp_id: str, body: ExperienceUpdateSchema) -> dict:
        exp = await Experience.objects.filter(id=exp_id).afirst()
        if not exp:
            raise NotFoundAPIError("Experience not found")

        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(exp, field, value)
        await exp.asave()
        return _serialize(exp)

    @staticmethod
    @jwt_required
    async def delete_experience(request, exp_id: str) -> dict:
        exp = await Experience.objects.filter(id=exp_id).afirst()
        if not exp:
            raise NotFoundAPIError("Experience not found")
        await exp.adelete()
        return {"message": "Experience deleted"}
