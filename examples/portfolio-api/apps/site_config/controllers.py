"""Site configuration endpoints."""

from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.router import get, patch

from .models import SiteConfig
from .schemas import SiteConfigOut, SiteConfigUpdate


class SiteConfigController(APIController):
    prefix = "/site-config"
    tags = ["Site Config"]

    @get("/")
    def get_config(self, request) -> SiteConfigOut:
        return SiteConfigOut.model_validate(SiteConfig.load())

    @patch("/")
    @jwt_required
    def update_config(self, request, body: SiteConfigUpdate) -> SiteConfigOut:
        config = SiteConfig.load()
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(config, field, value)
        config.save()
        return SiteConfigOut.model_validate(config)
