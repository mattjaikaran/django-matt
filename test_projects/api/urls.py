from django.urls import path
from django_matt import APIRouter

from .controllers import TaskController

# Create a router for the API
router = APIRouter(prefix="api/", tags=["tasks"])

# Register the TaskController
router.register_controller(TaskController)

# Get the URL patterns
urlpatterns = router.get_urls()
