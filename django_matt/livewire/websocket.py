"""
WebSocket support for Livewire components.

Enables real-time updates via WebSocket connections.
"""

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


# =============================================================================
# Connection Manager
# =============================================================================


@dataclass
class ComponentConnection:
    """Represents a WebSocket connection to a component."""

    connection_id: str
    component_id: str
    component_name: str
    user_id: str | None = None
    channel: Any | None = None


class ConnectionManager:
    """
    Manages WebSocket connections for Livewire components.

    Tracks which connections are subscribed to which components.
    """

    def __init__(self):
        self._connections: dict[str, ComponentConnection] = {}
        self._component_connections: dict[str, set[str]] = {}
        self._user_connections: dict[str, set[str]] = {}

    def register(self, connection: ComponentConnection):
        """Register a new connection."""
        self._connections[connection.connection_id] = connection

        # Track by component
        if connection.component_id not in self._component_connections:
            self._component_connections[connection.component_id] = set()
        self._component_connections[connection.component_id].add(connection.connection_id)

        # Track by user
        if connection.user_id:
            if connection.user_id not in self._user_connections:
                self._user_connections[connection.user_id] = set()
            self._user_connections[connection.user_id].add(connection.connection_id)

    def unregister(self, connection_id: str):
        """Unregister a connection."""
        connection = self._connections.pop(connection_id, None)
        if connection:
            # Remove from component tracking
            if connection.component_id in self._component_connections:
                self._component_connections[connection.component_id].discard(connection_id)
                if not self._component_connections[connection.component_id]:
                    del self._component_connections[connection.component_id]

            # Remove from user tracking
            if connection.user_id and connection.user_id in self._user_connections:
                self._user_connections[connection.user_id].discard(connection_id)
                if not self._user_connections[connection.user_id]:
                    del self._user_connections[connection.user_id]

    def get_connections_for_component(
        self,
        component_id: str,
    ) -> list[ComponentConnection]:
        """Get all connections for a component."""
        connection_ids = self._component_connections.get(component_id, set())
        return [self._connections[cid] for cid in connection_ids if cid in self._connections]

    def get_connections_for_user(
        self,
        user_id: str,
    ) -> list[ComponentConnection]:
        """Get all connections for a user."""
        connection_ids = self._user_connections.get(user_id, set())
        return [self._connections[cid] for cid in connection_ids if cid in self._connections]

    def get_all_connections(self) -> list[ComponentConnection]:
        """Get all active connections."""
        return list(self._connections.values())


# Global connection manager
connection_manager = ConnectionManager()


# =============================================================================
# WebSocket Consumer
# =============================================================================


class LivewireConsumer:
    """
    WebSocket consumer for Livewire components.

    Handles:
    - Component subscriptions
    - Action calls via WebSocket
    - Broadcasting updates to connected clients

    Usage with Django Channels:
        # routing.py
        from django.urls import path
        from django_matt.livewire import LivewireConsumer

        websocket_urlpatterns = [
            path('ws/livewire/', LivewireConsumer.as_asgi()),
        ]
    """

    def __init__(self, scope=None, receive=None, send=None):
        self.scope = scope or {}
        self.receive = receive
        self.send = send
        self.connection_id: str | None = None
        self._subscribed_components: set[str] = set()

    @classmethod
    def as_asgi(cls):
        """Return ASGI application."""

        async def app(scope, receive, send):
            consumer = cls(scope, receive, send)
            await consumer.run()

        return app

    async def run(self):
        """Main consumer loop."""
        import uuid

        self.connection_id = str(uuid.uuid4())

        try:
            while True:
                message = await self.receive()

                if message["type"] == "websocket.connect":
                    await self.connect()
                elif message["type"] == "websocket.disconnect":
                    await self.disconnect()
                    break
                elif message["type"] == "websocket.receive":
                    await self.receive_message(message.get("text", ""))
        except Exception:
            await self.disconnect()

    async def connect(self):
        """Handle WebSocket connection."""
        await self.send(
            {
                "type": "websocket.accept",
            }
        )

        await self.send_json(
            {
                "type": "connected",
                "connection_id": self.connection_id,
            }
        )

    async def disconnect(self):
        """Handle WebSocket disconnection."""
        # Unregister all subscriptions
        for component_id in self._subscribed_components:
            connection_manager.unregister(f"{self.connection_id}:{component_id}")

    async def receive_message(self, text: str):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(text)
            message_type = data.get("type")

            if message_type == "subscribe":
                await self.handle_subscribe(data)
            elif message_type == "unsubscribe":
                await self.handle_unsubscribe(data)
            elif message_type == "action":
                await self.handle_action(data)
            elif message_type == "update":
                await self.handle_update(data)
            elif message_type == "ping":
                await self.send_json({"type": "pong"})

        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as e:
            await self.send_error(str(e))

    async def handle_subscribe(self, data: dict):
        """Subscribe to a component's updates."""
        component_id = data.get("component_id")
        component_name = data.get("component_name")

        if not component_id or not component_name:
            await self.send_error("Missing component_id or component_name")
            return

        # Get user from scope
        user = self.scope.get("user")
        user_id = str(user.id) if user and hasattr(user, "id") else None

        # Register connection
        connection = ComponentConnection(
            connection_id=f"{self.connection_id}:{component_id}",
            component_id=component_id,
            component_name=component_name,
            user_id=user_id,
            channel=self,
        )
        connection_manager.register(connection)
        self._subscribed_components.add(component_id)

        await self.send_json(
            {
                "type": "subscribed",
                "component_id": component_id,
            }
        )

    async def handle_unsubscribe(self, data: dict):
        """Unsubscribe from a component's updates."""
        component_id = data.get("component_id")
        if component_id:
            connection_manager.unregister(f"{self.connection_id}:{component_id}")
            self._subscribed_components.discard(component_id)

            await self.send_json(
                {
                    "type": "unsubscribed",
                    "component_id": component_id,
                }
            )

    async def handle_action(self, data: dict):
        """Handle an action call via WebSocket."""
        from django_matt.livewire.registry import registry
        from django_matt.livewire.state import Snapshot

        snapshot_token = data.get("snapshot")
        action_name = data.get("action")
        params = data.get("params", [])

        if not snapshot_token or not action_name:
            await self.send_error("Missing snapshot or action")
            return

        try:
            # Restore component
            snapshot = Snapshot.from_token(snapshot_token)
            component_class = registry.get(snapshot.component_name)

            if not component_class:
                await self.send_error(f"Unknown component: {snapshot.component_name}")
                return

            component = component_class()
            component._component_id = snapshot.component_id
            component.hydrate(snapshot.state)

            # Call action
            result = component.call_action(action_name, *params)

            # Re-render
            html = component.to_html()

            # New snapshot
            new_snapshot = Snapshot(
                component_name=snapshot.component_name,
                component_id=snapshot.component_id,
                state=component.dehydrate(),
                checksum=component.get_checksum(),
            )

            await self.send_json(
                {
                    "type": "update",
                    "component_id": snapshot.component_id,
                    "html": html,
                    "snapshot": new_snapshot.to_token(),
                    "result": result
                    if isinstance(result, (dict, list, str, int, float, bool, type(None)))
                    else None,
                }
            )

        except Exception as e:
            await self.send_error(str(e))

    async def handle_update(self, data: dict):
        """Handle state update via WebSocket."""
        from django_matt.livewire.registry import registry
        from django_matt.livewire.state import Snapshot

        snapshot_token = data.get("snapshot")
        updates = data.get("updates", {})

        if not snapshot_token:
            await self.send_error("Missing snapshot")
            return

        try:
            snapshot = Snapshot.from_token(snapshot_token)
            component_class = registry.get(snapshot.component_name)

            if not component_class:
                await self.send_error(f"Unknown component: {snapshot.component_name}")
                return

            component = component_class()
            component._component_id = snapshot.component_id
            component.hydrate(snapshot.state)

            # Apply updates
            for key, value in updates.items():
                if hasattr(component, key):
                    setattr(component, key, value)

            # Re-render
            html = component.to_html()

            # New snapshot
            new_snapshot = Snapshot(
                component_name=snapshot.component_name,
                component_id=snapshot.component_id,
                state=component.dehydrate(),
                checksum=component.get_checksum(),
            )

            await self.send_json(
                {
                    "type": "update",
                    "component_id": snapshot.component_id,
                    "html": html,
                    "snapshot": new_snapshot.to_token(),
                }
            )

        except Exception as e:
            await self.send_error(str(e))

    async def send_json(self, data: dict):
        """Send JSON message."""
        await self.send(
            {
                "type": "websocket.send",
                "text": json.dumps(data),
            }
        )

    async def send_error(self, message: str):
        """Send error message."""
        await self.send_json(
            {
                "type": "error",
                "message": message,
            }
        )


# =============================================================================
# Broadcasting
# =============================================================================


async def broadcast_to(
    component_id: str,
    html: str,
    snapshot_token: str,
    effects: dict | None = None,
):
    """
    Broadcast an update to all connections watching a component.

    Usage:
        await broadcast_to(
            component_id="abc123",
            html=rendered_html,
            snapshot_token=snapshot.to_token(),
        )
    """
    connections = connection_manager.get_connections_for_component(component_id)

    message = {
        "type": "update",
        "component_id": component_id,
        "html": html,
        "snapshot": snapshot_token,
    }
    if effects:
        message["effects"] = effects

    for connection in connections:
        if connection.channel:
            try:
                await connection.channel.send_json(message)
            except Exception:
                # Connection might be closed
                pass


async def broadcast_to_user(
    user_id: str,
    event: str,
    data: dict,
):
    """
    Broadcast an event to all of a user's connections.

    Usage:
        await broadcast_to_user(
            user_id="123",
            event="notification",
            data={"message": "You have a new message"},
        )
    """
    connections = connection_manager.get_connections_for_user(user_id)

    message = {
        "type": "event",
        "event": event,
        "data": data,
    }

    for connection in connections:
        if connection.channel:
            try:
                await connection.channel.send_json(message)
            except Exception:
                pass


async def broadcast_to_all(
    event: str,
    data: dict,
    component_name: str | None = None,
):
    """
    Broadcast an event to all connections.

    Args:
        event: Event name
        data: Event data
        component_name: Only broadcast to connections for this component type
    """
    connections = connection_manager.get_all_connections()

    if component_name:
        connections = [c for c in connections if c.component_name == component_name]

    message = {
        "type": "event",
        "event": event,
        "data": data,
    }

    for connection in connections:
        if connection.channel:
            try:
                await connection.channel.send_json(message)
            except Exception:
                pass


__all__ = [
    "ComponentConnection",
    "ConnectionManager",
    "LivewireConsumer",
    "broadcast_to",
    "broadcast_to_all",
    "broadcast_to_user",
    "connection_manager",
]
