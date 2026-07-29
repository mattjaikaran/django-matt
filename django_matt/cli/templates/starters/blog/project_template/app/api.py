"""Main API configuration for {{ project_name }} blog."""

from django_matt import DjangoMattAPI

from {{ project_name }}_app.comments.controllers import CommentController
from {{ project_name }}_app.posts.controllers import PostController, TagController
from {{ project_name }}_app.users.controllers import AuthController

api = DjangoMattAPI(
    title="{{ project_name }} Blog API",
    version="1.0.0",
    description="Blog API built with django-matt. JWT auth, search, tagging.",
)

api.register_controller(AuthController)
api.register_controller(PostController)
api.register_controller(TagController)
api.register_controller(CommentController)
