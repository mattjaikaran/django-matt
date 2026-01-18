"""
Livewire-style Reactivity System.

Provides reactive Python components that can update in real-time
via WebSocket, similar to Laravel Livewire or Phoenix LiveView.

Usage:
    from django_matt.livewire import LiveComponent, reactive, action

    class Counter(LiveComponent):
        count: int = 0

        @action
        def increment(self):
            self.count += 1

        @action
        def decrement(self):
            self.count -= 1

        def render(self):
            return f'''
            <div>
                <span>{self.count}</span>
                <button wire:click="increment">+</button>
                <button wire:click="decrement">-</button>
            </div>
            '''
"""

from django_matt.livewire.component import (
    LiveComponent,
    reactive,
    computed,
    watch,
    action,
    on_mount,
    on_hydrate,
    on_dehydrate,
)
from django_matt.livewire.state import (
    State,
    StateManager,
    Snapshot,
)
from django_matt.livewire.middleware import (
    LivewireMiddleware,
    AsyncLivewireMiddleware,
)
from django_matt.livewire.views import (
    livewire_message,
    livewire_upload,
    LivewireView,
)
from django_matt.livewire.registry import (
    ComponentRegistry,
    registry,
    register_component,
)
from django_matt.livewire.websocket import (
    LivewireConsumer,
    broadcast_to,
    broadcast_to_all,
)

__all__ = [
    # Component
    "LiveComponent",
    "reactive",
    "computed",
    "watch",
    "action",
    "on_mount",
    "on_hydrate",
    "on_dehydrate",
    # State
    "State",
    "StateManager",
    "Snapshot",
    # Middleware
    "LivewireMiddleware",
    "AsyncLivewireMiddleware",
    # Views
    "livewire_message",
    "livewire_upload",
    "LivewireView",
    # Registry
    "ComponentRegistry",
    "registry",
    "register_component",
    # WebSocket
    "LivewireConsumer",
    "broadcast_to",
    "broadcast_to_all",
]
