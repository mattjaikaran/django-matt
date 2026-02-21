"""
Views for handling Livewire requests.

Provides endpoints for component updates, actions, and file uploads.
"""

from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

import orjson

from django_matt.livewire.component import LiveComponent
from django_matt.livewire.registry import registry
from django_matt.livewire.state import Snapshot


def livewire_message(request: HttpRequest) -> JsonResponse:
    """
    Handle Livewire component update requests.

    This is the main endpoint for:
    - Calling actions
    - Updating state (wire:model)
    - Getting re-rendered HTML

    Expected POST data:
    {
        "_snapshot": "...",  // Component state token
        "_action": "methodName",  // Action to call (optional)
        "_params": [...],  // Action parameters
        "_updates": {...},  // State updates (wire:model)
    }

    Returns:
    {
        "html": "...",  // Re-rendered component HTML
        "snapshot": "...",  // New state token
        "effects": {...},  // Side effects (redirects, events, etc.)
    }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        # Parse request data
        data = (
            orjson.loads(request.body) if request.content_type == "application/json" else request.POST
        )

        snapshot_token = data.get("_snapshot")
        action_name = data.get("_action")
        action_params = data.get("_params", [])
        state_updates = data.get("_updates", {})

        # Restore component from snapshot
        if not snapshot_token:
            return JsonResponse({"error": "Missing snapshot"}, status=400)

        try:
            snapshot = Snapshot.from_token(snapshot_token)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)

        # Get component class
        component_class = registry.get(snapshot.component_name)
        if component_class is None:
            return JsonResponse(
                {"error": f"Unknown component: {snapshot.component_name}"},
                status=400,
            )

        # Create and hydrate component
        component = component_class()
        component._component_id = snapshot.component_id
        component._request = request
        component.hydrate(snapshot.state)

        # Apply state updates (wire:model)
        for key, value in state_updates.items():
            if hasattr(component, key):
                setattr(component, key, value)

        # Call action if specified
        effects: dict[str, Any] = {}
        if action_name:
            try:
                result = component.call_action(action_name, *action_params)

                # Handle special return values
                if isinstance(result, dict):
                    effects.update(result)
            except Exception as e:
                effects["error"] = str(e)

        # Re-render component
        html = component.to_html()

        # Create new snapshot
        new_snapshot = Snapshot(
            component_name=snapshot.component_name,
            component_id=snapshot.component_id,
            state=component.dehydrate(),
            checksum=component.get_checksum(),
        )

        return JsonResponse(
            {
                "html": html,
                "snapshot": new_snapshot.to_token(),
                "effects": effects,
            }
        )

    except orjson.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def livewire_upload(request: HttpRequest) -> JsonResponse:
    """
    Handle file uploads for Livewire components.

    Files are temporarily stored and a reference is returned
    that can be used to complete the upload in an action.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    if not request.FILES:
        return JsonResponse({"error": "No files provided"}, status=400)

    import uuid

    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    uploaded_files = []

    for field_name, uploaded_file in request.FILES.items():
        # Generate temporary path
        temp_id = str(uuid.uuid4())
        temp_path = f"livewire-tmp/{temp_id}/{uploaded_file.name}"

        # Save temporarily
        saved_path = default_storage.save(temp_path, ContentFile(uploaded_file.read()))

        uploaded_files.append(
            {
                "id": temp_id,
                "name": uploaded_file.name,
                "size": uploaded_file.size,
                "type": uploaded_file.content_type,
                "path": saved_path,
            }
        )

    return JsonResponse(
        {
            "files": uploaded_files,
        }
    )


@method_decorator(csrf_exempt, name="dispatch")
class LivewireView(View):
    """
    Class-based view for Livewire components.

    Usage:
        # urls.py
        path('livewire/<str:component>/', LivewireView.as_view()),

        # Or for a specific component
        class CounterView(LivewireView):
            component_class = Counter
    """

    component_class: type[LiveComponent] | None = None
    component_name: str | None = None

    def get_component_class(self, request: HttpRequest, **kwargs) -> type[LiveComponent]:
        """Get the component class to use."""
        if self.component_class:
            return self.component_class

        # Try to get from URL kwargs
        component_name = kwargs.get("component") or self.component_name
        if component_name:
            cls = registry.get(component_name)
            if cls:
                return cls

        raise ValueError("No component class specified")

    def get(self, request: HttpRequest, **kwargs) -> HttpResponse:
        """
        Initial render of the component.

        Returns full HTML that can be embedded in a page.
        """
        component_class = self.get_component_class(request, **kwargs)

        # Get initial props from query params
        props = {k: v for k, v in request.GET.items() if not k.startswith("_")}

        # Create component
        component = component_class(**props)
        component._request = request
        component.mount()

        # Create snapshot
        snapshot = Snapshot(
            component_name=component._component_name,
            component_id=component._component_id,
            state=component.dehydrate(),
            checksum=component.get_checksum(),
        )

        # Render with wrapper
        html = self._render_with_wrapper(component, snapshot)

        return HttpResponse(html, content_type="text/html")

    def post(self, request: HttpRequest, **kwargs) -> JsonResponse:
        """Handle component updates (actions, state changes)."""
        return livewire_message(request)

    def _render_with_wrapper(
        self,
        component: LiveComponent,
        snapshot: Snapshot,
    ) -> str:
        """Render component with Livewire wrapper attributes."""
        inner_html = component.to_html()

        return f'''
<div
    wire:id="{component.component_id}"
    wire:snapshot="{snapshot.to_token()}"
    wire:effects="[]"
>
{inner_html}
</div>
'''


def render_component(
    component: LiveComponent,
    request: HttpRequest | None = None,
) -> str:
    """
    Render a component to HTML with Livewire wrapper.

    Usage:
        counter = Counter(count=5)
        html = render_component(counter, request)
    """
    if request:
        component._request = request

    if not component._mounted:
        component.mount()

    snapshot = Snapshot(
        component_name=component._component_name,
        component_id=component._component_id,
        state=component.dehydrate(),
        checksum=component.get_checksum(),
    )

    inner_html = component.to_html()

    return f'''
<div
    wire:id="{component.component_id}"
    wire:snapshot="{snapshot.to_token()}"
    wire:effects="[]"
>
{inner_html}
</div>
'''


__all__ = [
    "LivewireView",
    "livewire_message",
    "livewire_upload",
    "render_component",
]
