from django.urls import path

from {{ project_name }}_app.api import api

urlpatterns = [
    path("api/", api.urls),
]
