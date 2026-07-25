from django_matt import DjangoMattAPI

from apps.skills.schemas import SkillSchema

from .skill_controller import SkillController


def register_skill_routes(api: DjangoMattAPI) -> None:
    api.get("skills", tags=["Skills"])(SkillController.list_skills)

    api.post("skills", response_model=SkillSchema, status_code=201, tags=["Skills"])(
        SkillController.create_skill
    )

    api.get("skills/<str:skill_id>", response_model=SkillSchema, tags=["Skills"])(
        SkillController.get_skill
    )

    api.patch("skills/<str:skill_id>", response_model=SkillSchema, tags=["Skills"])(
        SkillController.update_skill
    )

    api.delete("skills/<str:skill_id>", tags=["Skills"])(SkillController.delete_skill)
