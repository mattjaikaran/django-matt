"""Main API configuration for blog."""

from django_matt import MattAPI

from blog.comments.controllers import CommentController
from blog.posts.controllers import CategoryController, PostController, TagController
from blog.users.controllers import AuthController, AuthorController

api = MattAPI(
    title="Blog API",
    version="1.0.0",
    description="Full-featured blog API built with django-matt. JWT auth, full-text search, RSS, SEO endpoints.",
    prefix="/api",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

api.register_controller(AuthController)
api.register_controller(AuthorController)
api.register_controller(PostController)
api.register_controller(TagController)
api.register_controller(CategoryController)
api.register_controller(CommentController)
