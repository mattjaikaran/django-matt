"""
django-matt service layer.

Provides base classes for:
- Internal CRUD services (BaseService, CRUDService)
- Third-party HTTP service clients (BaseThirdPartyService, ThirdPartyServiceError)

Not auto-loaded. Import explicitly:

    from django_matt.services import CRUDService, BaseThirdPartyService

Pattern:

    # myapp/services.py
    class ProductService(CRUDService["Product"]):
        model = Product

        def get_queryset(self):
            return super().get_queryset().select_related("category")

    # myapp/controllers.py
    class ProductController(APIController):
        prefix = "/products"

        def __init__(self):
            self.service = ProductService()
            super().__init__()

        @api.get("/")
        async def list_products(self, request):
            items, total = await self.service.list()
            return {"items": items, "total": total}

        @api.post("/")
        async def create_product(self, request, data: ProductCreateSchema):
            return await self.service.create(data.model_dump(), user=request.user)
"""

from django_matt.services.base import (
    BaseService,
    ConflictError,
    CRUDService,
    NotFoundError,
    ServiceError,
    ValidationError,
)
from django_matt.services.third_party import (
    BaseThirdPartyService,
    ThirdPartyServiceError,
)

__all__ = [
    # Internal services
    "BaseService",
    "CRUDService",
    # Service exceptions
    "ServiceError",
    "NotFoundError",
    "ValidationError",
    "ConflictError",
    # Third-party services
    "BaseThirdPartyService",
    "ThirdPartyServiceError",
]
