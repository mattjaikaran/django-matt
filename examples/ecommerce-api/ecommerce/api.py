"""Main API configuration for e-commerce."""

from django_matt import MattAPI

from ecommerce.cart.controllers import CartController
from ecommerce.catalog.controllers import CategoryController, ProductController
from ecommerce.orders.controllers import CouponController, OrderController
from ecommerce.payments.controllers import PaymentController, WebhookController
from ecommerce.reviews.controllers import ReviewController
from ecommerce.users.controllers import AddressController, AuthController, WishlistController

# Initialize the API
api = MattAPI(
    title="E-Commerce API",
    version="1.0.0",
    description="Production-quality e-commerce backend API built with django-matt",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Register controllers
api.register_controller(AuthController)
api.register_controller(ProductController)
api.register_controller(CategoryController)
api.register_controller(CartController)
api.register_controller(OrderController)
api.register_controller(PaymentController)
api.register_controller(WebhookController)
api.register_controller(ReviewController)
api.register_controller(WishlistController)
api.register_controller(AddressController)
api.register_controller(CouponController)
