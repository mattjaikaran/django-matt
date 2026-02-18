"""Custom action decorator for resource endpoints."""

from collections.abc import Callable


class ActionDescriptor:
    """Stores metadata about a custom action on a resource."""

    def __init__(
        self,
        method: str,
        path: str,
        *,
        permissions: list | None = None,
        summary: str | None = None,
        tags: list[str] | None = None,
    ):
        self.method = method.upper()
        self.path = path
        self.permissions = permissions
        self.summary = summary
        self.tags = tags
        self.handler: Callable | None = None

    def __call__(self, func: Callable) -> "ActionDescriptor":
        self.handler = func
        self.handler_name = func.__name__
        return self


def action(
    method: str = "POST",
    path: str = "",
    *,
    permissions: list | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
) -> ActionDescriptor:
    """
    Decorator to add a custom endpoint to a resource.

    Usage:
        @resource(api, prefix="/products")
        class ProductResource:
            model = Product

            @action("POST", "/bulk-import", permissions=[IsAdmin])
            async def bulk_import(self, request, data: BulkImportSchema):
                ...
    """
    return ActionDescriptor(
        method=method,
        path=path,
        permissions=permissions,
        summary=summary,
        tags=tags,
    )
