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
        "from django_matt.core.controller import APIController",
        "from django_matt.core.router import get, post, put, patch, delete",
        "from django_matt.permissions import IsAuthenticated",
        "",
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
        lines.extend(_generate_basic_endpoints(name, name_plural))

    return "\n".join(lines)


def _generate_crud_endpoints(name: str, name_lower: str, name_plural: str) -> list[str]:
    """Generate full CRUD endpoint methods."""
    return [
        '    @get("/")',
        f"    async def list_{name_plural}(self, request, page: int = 1, page_size: int = 20):",
        f'        """List all {name} objects."""',
        "        # TODO: Implement list logic",
        '        return {"items": [], "total": 0, "page": page, "page_size": page_size}',
        "",
        '    @get("/{id}")',
        f"    async def get_{name_lower}(self, request, id: int) -> {name}Schema:",
        f'        """Get a single {name} by ID."""',
        "        # TODO: Implement get logic",
        "        pass",
        "",
        '    @post("/")',
        f"    async def create_{name_lower}(",
        "        self,",
        "        request,",
        f"        data: {name}CreateSchema,",
        f"    ) -> {name}Schema:",
        f'        """Create a new {name}."""',
        "        # TODO: Implement create logic",
        "        pass",
        "",
        '    @put("/{id}")',
        f"    async def update_{name_lower}(",
        "        self,",
        "        request,",
        "        id: int,",
        f"        data: {name}UpdateSchema,",
        f"    ) -> {name}Schema:",
        f'        """Update a {name}."""',
        "        # TODO: Implement update logic",
        "        pass",
        "",
        '    @delete("/{id}")',
        f"    async def delete_{name_lower}(self, request, id: int) -> dict:",
        f'        """Delete a {name}."""',
        "        # TODO: Implement delete logic",
        '        return {"success": True}',
    ]


def _generate_basic_endpoints(name: str, name_plural: str) -> list[str]:
    """Generate basic list endpoint."""
    return [
        '    @get("/")',
        f"    async def list_{name_plural}(self, request):",
        f'        """List all {name} objects."""',
        "        # TODO: Implement your logic here",
        '        return {"items": []}',
        "",
        "    # Add more endpoints as needed",
    ]
