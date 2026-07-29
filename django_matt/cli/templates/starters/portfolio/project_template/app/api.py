"""Main API configuration for {{ project_name }} portfolio."""

from django_matt import DjangoMattAPI

from {{ project_name }}_app.projects.controllers import ProjectController
from {{ project_name }}_app.skills.controllers import SkillController
from {{ project_name }}_app.experience.controllers import ExperienceController
from {{ project_name }}_app.contact.controllers import ContactController

api = DjangoMattAPI(
    title="{{ project_name }} API",
    version="1.0.0",
    description="Portfolio API built with django-matt. Public read, admin write with JWT auth.",
)

api.register_controller(ProjectController)
api.register_controller(SkillController)
api.register_controller(ExperienceController)
api.register_controller(ContactController)
