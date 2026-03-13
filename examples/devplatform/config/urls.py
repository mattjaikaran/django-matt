from django.contrib import admin
from django.urls import include, path

from api.main import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api.urls)),
]
