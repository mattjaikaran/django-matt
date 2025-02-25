from django_matt import APIRouter

from .controllers import TodoController

# Create a router for the todo app
router = APIRouter(prefix="api/", tags=["todos"])

# Register the TodoController
router.register_controller(TodoController)

# Get the URL patterns
urlpatterns = router.get_urls()
