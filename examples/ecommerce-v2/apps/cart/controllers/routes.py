from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_matt.api import DjangoMattAPI

from apps.cart.controllers.cart_controller import CartController


def register_cart_routes(api: DjangoMattAPI) -> None:
    """Register cart routes with the API."""
    controller = CartController()

    api.get("cart", tags=["Cart"])(controller.get_cart)
    api.post("cart/items", status_code=201, tags=["Cart"])(controller.add_to_cart)
    api.patch("cart/items/<str:item_id>", tags=["Cart"])(controller.update_cart_item)
    api.delete("cart/items/<str:item_id>", tags=["Cart"])(controller.remove_cart_item)
    api.delete("cart", tags=["Cart"])(controller.clear_cart)
