"""
Controller template generation.
"""

from django_matt.cli.templates.utils import pluralize


def generate_controller_template(name: str, crud: bool = False) -> str:
    """
    Generate a controller template.

    Args:
        name: The model/resource name (e.g., "Product", "User")
        crud: If True, generate full CRUD endpoints

    Returns:
        Python code for the controller
    """
    name_lower = name.lower()
    name_plural = pluralize(name_lower)

    lines = [
        '"""',
        f"{name} API Controller.",
        '"""',
        "",
        "from django.http import Http404",
        "",
        "from django_matt.core.controller import APIController",
        "from django_matt.core.router import get, post, put, delete",
        "from django_matt.permissions import IsAuthenticated",
        "",
        f"from .models import {name}",
        f"from .{name_lower}_schemas import (",
        f"    {name}Schema,",
        f"    {name}CreateSchema,",
        f"    {name}UpdateSchema,",
        ")",
        "",
        "",
        f"class {name}Controller(APIController):",
        f'    """Controller for {name} operations."""',
        "",
        f'    prefix = "/{name_plural}"',
        f'    tags = ["{name}"]',
        "    permission_classes = [IsAuthenticated]",
        "",
    ]

    if crud:
        lines.extend(_generate_crud_endpoints(name, name_lower, name_plural))
    else:
        lines.extend(_generate_basic_endpoints(name, name_lower, name_plural))

    return "\n".join(lines)


def _generate_crud_endpoints(name: str, name_lower: str, name_plural: str) -> list[str]:
    """Generate full CRUD endpoint methods."""
    return [
        '    @get("/")',
        f"    async def list_{name_plural}(self, request, page: int = 1, page_size: int = 20):",
        f'        """List all {name} objects."""',
        f"        queryset = {name}.objects.all()",
        "        total = await queryset.acount()",
        "        offset = (page - 1) * page_size",
        "        items = [item async for item in queryset[offset:offset + page_size]]",
        '        return {"items": items, "total": total, "page": page, "page_size": page_size}',
        "",
        '    @get("/{id}")',
        f"    async def get_{name_lower}(self, request, id: int) -> {name}Schema:",
        f'        """Get a single {name} by ID."""',
        "        try:",
        f"            return await {name}.objects.aget(pk=id)",
        f"        except {name}.DoesNotExist:",
        f'            raise Http404(f"{name} {{id}} not found")',
        "",
        '    @post("/")',
        f"    async def create_{name_lower}(",
        "        self,",
        "        request,",
        f"        data: {name}CreateSchema,",
        f"    ) -> {name}Schema:",
        f'        """Create a new {name}."""',
        f"        return await {name}.objects.acreate(**data.model_dump())",
        "",
        '    @put("/{id}")',
        f"    async def update_{name_lower}(",
        "        self,",
        "        request,",
        "        id: int,",
        f"        data: {name}UpdateSchema,",
        f"    ) -> {name}Schema:",
        f'        """Update a {name}."""',
        "        try:",
        f"            item = await {name}.objects.aget(pk=id)",
        f"        except {name}.DoesNotExist:",
        f'            raise Http404(f"{name} {{id}} not found")',
        "        for key, value in data.model_dump(exclude_unset=True).items():",
        "            setattr(item, key, value)",
        "        await item.asave()",
        "        return item",
        "",
        '    @delete("/{id}")',
        f"    async def delete_{name_lower}(self, request, id: int) -> dict:",
        f'        """Delete a {name}."""',
        "        try:",
        f"            item = await {name}.objects.aget(pk=id)",
        f"        except {name}.DoesNotExist:",
        f'            raise Http404(f"{name} {{id}} not found")',
        "        await item.adelete()",
        '        return {"success": True}',
    ]


def _generate_basic_endpoints(name: str, name_lower: str, name_plural: str) -> list[str]:
    """Generate basic list and detail endpoints."""
    return [
        '    @get("/")',
        f"    async def list_{name_plural}(self, request):",
        f'        """List all {name} objects."""',
        f"        items = [{name_lower} async for {name_lower} in {name}.objects.all()]",
        '        return {"items": items}',
        "",
        '    @get("/{id}")',
        f"    async def get_{name_lower}(self, request, id: int) -> {name}Schema:",
        f'        """Get a single {name} by ID."""',
        "        try:",
        f"            return await {name}.objects.aget(pk=id)",
        f"        except {name}.DoesNotExist:",
        f'            raise Http404(f"{name} {{id}} not found")',
    ]
