from django_matt import DjangoMattAPI
from django_matt.auth import jwt_required

from apps.cart.controllers import register_cart_routes
from apps.catalog.controllers import register_catalog_routes
from apps.orders.controllers import register_order_routes
from apps.payments.controllers import register_payment_routes
from apps.reviews.controllers import register_review_routes
from apps.search.controllers import register_search_routes
from apps.stores.controllers import register_store_routes
from apps.users.controllers import register_auth_routes

api = DjangoMattAPI(
    title="Ecommerce API",
    version="1.0.0",
    description="Multi-vendor marketplace built with django-matt",
)

# Register all routes
register_auth_routes(api)
register_store_routes(api)
register_catalog_routes(api)
register_cart_routes(api)
register_order_routes(api)
register_payment_routes(api)
register_review_routes(api)
register_search_routes(api)


@api.get("health", tags=["Health"])
async def health_check(request) -> dict:
    return {"status": "healthy"}


@api.get("protected", tags=["Health"])
@jwt_required
async def protected_endpoint(request) -> dict:
    return {"message": f"Hello, {request.user.email}!"}
