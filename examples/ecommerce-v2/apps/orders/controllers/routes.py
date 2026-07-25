from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_matt.api import DjangoMattAPI

from apps.orders.controllers.order_controller import OrderController


def register_order_routes(api: DjangoMattAPI) -> None:
    """Register order routes with the API."""
    controller = OrderController()

    api.get("orders", tags=["Orders"])(controller.list_orders)
    api.post("orders", tags=["Orders"])(controller.create_order)
    api.get("orders/<str:order_id>", tags=["Orders"])(controller.get_order)
    api.patch("orders/<str:order_id>", tags=["Orders"])(controller.update_order_status)
    api.post("orders/<str:order_id>/cancel", status_code=200, tags=["Orders"])(
        controller.cancel_order
    )
