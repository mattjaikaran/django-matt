from django.contrib import admin
from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.urls import include, path, re_path

from apps.api import api


def spa_index(request, path=""):
    index = settings.BASE_DIR / "frontend_dist" / "index.html"
    if index.exists():
        return FileResponse(open(index, "rb"), content_type="text/html")
    return HttpResponse("Frontend not built. Run: bun run build", status=503)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api.urls)),
    # Catch-all: hand every non-API route to the React SPA
    re_path(r"^(?!api/|admin/|static/).*$", spa_index),
]
