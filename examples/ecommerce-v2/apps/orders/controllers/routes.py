from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_matt.api import MattAPI

from apps.orders.controllers.order_controller import OrderController


def register_order_routes(api: MattAPI) -> None:
    """Register order routes with the API."""
    api.get("orders", tags=["Orders"])(OrderController.list_orders)
    api.post("orders", tags=["Orders"])(OrderController.create_order)
    api.get("orders/<str:order_id>", tags=["Orders"])(OrderController.get_order)
    api.patch("orders/<str:order_id>", tags=["Orders"])(OrderController.update_order_status)
    api.post("orders/<str:order_id>/cancel", status_code=200, tags=["Orders"])(
        OrderController.cancel_order
    )
