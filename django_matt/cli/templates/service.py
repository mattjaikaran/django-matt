"""
Service template generation.
"""


def generate_service_template(name: str) -> str:
    """
    Generate a service layer template that inherits from CRUDService.

    Args:
        name: The model/resource name (e.g., "Product", "User")

    Returns:
        Python code for the service
    """
    name_lower = name.lower()

    lines = [
        '"""',
        f"{name} Service Layer.",
        "",
        f"Contains business logic for {name} operations.",
        "Keep controllers thin — they should only handle HTTP concerns.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from django_matt.services import CRUDService",
        "",
        f"from .models import {name}",
        "",
        "",
        f'class {name}Service(CRUDService["{name}"]):',
        f'    """Business logic for {name}."""',
        "",
        f"    model = {name}",
        "",
        "    def get_queryset(self):",
        '        """Override to add select_related, default ordering, etc."""',
        "        return super().get_queryset()",
        "",
        "    # ------------------------------------------------------------------",
        "    # Domain methods (add your custom business logic below)",
        "    # ------------------------------------------------------------------",
        "",
        f"    # async def get_active_{name_lower}s(self):",
        f'    #     """Return only active {name_lower}s."""',
        "    #     return await self.all(is_active=True)",
        "",
    ]

    return "\n".join(lines)


def generate_third_party_service_template(name: str, base_url: str = "") -> str:
    """
    Generate a third-party service template that inherits from BaseThirdPartyService.

    Args:
        name: The service name (e.g., "Stripe", "Resend")
        base_url: The service's base URL

    Returns:
        Python code for the service
    """
    name_lower = name.lower()

    lines = [
        '"""',
        f"{name} service client.",
        "",
        f"Wraps the {name} HTTP API.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from django.conf import settings",
        "",
        "from django_matt.services import BaseThirdPartyService, ThirdPartyServiceError",
        "",
        "",
        f"class {name}Service(BaseThirdPartyService):",
        f'    """{name} API client."""',
        "",
        f'    base_url = "{base_url}"',
        "",
        "    def _auth_headers(self) -> dict:",
        f'        """Return {name} auth headers."""',
        f'        api_key = getattr(settings, "{name.upper()}_API_KEY", "")',
        '        return {"Authorization": f"Bearer {api_key}"}',
        "",
        "    # ------------------------------------------------------------------",
        "    # API methods",
        "    # ------------------------------------------------------------------",
        "",
        "    # async def example_call(self, param: str) -> dict:",
        '    #     """Example API call."""',
        '    #     return await self._post("/endpoint", {"param": param})',
        "",
    ]

    return "\n".join(lines)
