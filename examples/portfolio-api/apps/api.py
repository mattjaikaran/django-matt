from django_matt import MattAPI

from apps.contact.controllers import register_contact_routes
from apps.experience.controllers import register_experience_routes
from apps.projects.controllers import register_project_routes
from apps.skills.controllers import register_skill_routes
from apps.users.controllers import register_auth_routes

api = MattAPI(
    title="Portfolio API",
    version="1.0.0",
    description="Personal portfolio backend built with django-matt",
)

register_auth_routes(api)
register_project_routes(api)
register_skill_routes(api)
register_experience_routes(api)
register_contact_routes(api)


@api.get("health", tags=["Health"])
async def health_check(request) -> dict:
    return {"status": "healthy"}
