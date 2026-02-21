"""
Service template generation.
"""


def generate_service_template(name: str) -> str:
    """
    Generate a service layer template.

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
        "Keep controllers thin - they should only handle HTTP concerns.",
        '"""',
        "",
        "from django.http import Http404",
        "",
        f"from .models import {name}",
        f"from .{name_lower}_schemas import {name}CreateSchema, {name}UpdateSchema",
        "",
        "",
        f"class {name}Service:",
        f'    """Service for {name} business logic."""',
        "",
    ]

    lines.extend(_generate_list_method(name))
    lines.extend(_generate_get_method(name))
    lines.extend(_generate_create_method(name))
    lines.extend(_generate_update_method(name))
    lines.extend(_generate_delete_method(name))

    return "\n".join(lines)


def _generate_list_method(name: str) -> list[str]:
    """Generate the list method."""
    return [
        "    async def list(self, page: int = 1, page_size: int = 20, **filters):",
        f'        """List {name} objects with pagination."""',
        f"        queryset = {name}.objects.all()",
        "        for key, value in filters.items():",
        "            if value is not None:",
        "                queryset = queryset.filter(**{key: value})",
        "        total = await queryset.acount()",
        "        offset = (page - 1) * page_size",
        "        items = [item async for item in queryset[offset:offset + page_size]]",
        "        return items, total",
        "",
    ]


def _generate_get_method(name: str) -> list[str]:
    """Generate the get method."""
    return [
        "    async def get(self, id: int):",
        f'        """Get a single {name} by ID."""',
        "        try:",
        f"            return await {name}.objects.aget(pk=id)",
        f"        except {name}.DoesNotExist:",
        f'            raise Http404(f"{name} {{id}} not found")',
        "",
    ]


def _generate_create_method(name: str) -> list[str]:
    """Generate the create method."""
    return [
        f"    async def create(self, data: {name}CreateSchema, user=None):",
        f'        """Create a new {name}."""',
        "        create_data = data.model_dump()",
        f"        return await {name}.objects.acreate(**create_data)",
        "",
    ]


def _generate_update_method(name: str) -> list[str]:
    """Generate the update method."""
    return [
        f"    async def update(self, id: int, data: {name}UpdateSchema, partial: bool = False):",
        f'        """Update a {name}."""',
        "        item = await self.get(id)",
        "        update_data = data.model_dump(exclude_unset=partial)",
        "        for key, value in update_data.items():",
        "            setattr(item, key, value)",
        "        await item.asave()",
        "        return item",
        "",
    ]


def _generate_delete_method(name: str) -> list[str]:
    """Generate the delete method."""
    return [
        "    async def delete(self, id: int) -> bool:",
        f'        """Delete a {name}."""',
        "        item = await self.get(id)",
        "        await item.adelete()",
        "        return True",
    ]
