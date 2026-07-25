from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django_matt.core import APIController

from apps.catalog.models import Product
from apps.search.schemas import SearchResponseSchema, SearchResultSchema


class SearchController(APIController):
    prefix = "/search"
    tags = ["Search"]

    @staticmethod
    async def search(request) -> dict:
        """Search products by keyword with optional filters."""
        params = request.GET
        query = params.get("q", "").strip()
        result_type = params.get("type", "product")
        category_id = params.get("category")
        min_price = params.get("min_price")
        max_price = params.get("max_price")
        limit = min(int(params.get("limit", "20")), 100)
        offset = int(params.get("offset", "0"))

        qs = Product.objects.filter(is_active=True)

        # Keyword search
        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))

        # Category filter
        if category_id:
            qs = qs.filter(category_id=category_id)

        # Price range filters
        if min_price:
            try:
                qs = qs.filter(price__gte=Decimal(min_price))
            except (InvalidOperation, ValueError):
                pass

        if max_price:
            try:
                qs = qs.filter(price__lte=Decimal(max_price))
            except (InvalidOperation, ValueError):
                pass

        total = await qs.acount()
        products_qs = qs.order_by("-created_at")[offset : offset + limit]

        results = []
        async for product in products_qs:
            results.append(
                SearchResultSchema(
                    id=str(product.id),
                    name=product.name,
                    type=result_type,
                    description=product.description,
                    price=float(product.price),
                    image_url=product.image_url,
                    url=f"/api/products/{product.id}",
                ).model_dump(mode="json")
            )

        return SearchResponseSchema(
            results=results,
            total=total,
            query=query,
        ).model_dump(mode="json")
