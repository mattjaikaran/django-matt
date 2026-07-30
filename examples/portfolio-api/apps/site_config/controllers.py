"""Site configuration endpoints."""

from django.http import HttpRequest

from django_matt.core.controller import APIController, api_controller
from django_matt.core.router import get, patch, router

from .models import SiteConfig
from .schemas import SiteConfigOut, SiteConfigUpdate


@api_controller("site-config", tags=["Site Config"])
class SiteConfigController(APIController):
    """Public and admin endpoints for site configuration."""

    @get("/", response=SiteConfigOut)
    def get_config(self, request: HttpRequest) -> SiteConfig:
        """Get the public site configuration."""
        return SiteConfig.load()

    @patch("/", response=SiteConfigOut, auth=True)
    def update_config(self, request: HttpRequest, data: SiteConfigUpdate) -> SiteConfig:
        """Update site configuration (admin only)."""
        config = SiteConfig.load()
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(config, field, value)
        config.save()
        return config
