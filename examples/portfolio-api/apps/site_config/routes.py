"""SiteConfig route registration."""

from django_matt import DjangoMattAPI

from .controllers import SiteConfigController
from .schemas import SiteConfigOut


def register_site_config_routes(api: DjangoMattAPI) -> None:
    api.get("site-config", response_model=SiteConfigOut, tags=["Site Config"])(
        SiteConfigController.get_config
    )

    api.patch("site-config", response_model=SiteConfigOut, tags=["Site Config"])(
        SiteConfigController.update_config
    )
