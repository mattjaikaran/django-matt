from django_matt import DjangoMattAPI

from apps.experience.schemas import ExperienceSchema

from .experience_controller import ExperienceController


def register_experience_routes(api: DjangoMattAPI) -> None:
    api.get("experience", tags=["Experience"])(ExperienceController.list_experience)

    api.post("experience", response_model=ExperienceSchema, status_code=201, tags=["Experience"])(
        ExperienceController.create_experience
    )

    api.get("experience/<str:exp_id>", response_model=ExperienceSchema, tags=["Experience"])(
        ExperienceController.get_experience
    )

    api.patch("experience/<str:exp_id>", response_model=ExperienceSchema, tags=["Experience"])(
        ExperienceController.update_experience
    )

    api.delete("experience/<str:exp_id>", tags=["Experience"])(
        ExperienceController.delete_experience
    )
