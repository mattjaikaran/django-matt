"""
Views for the chat frontend demo.

These are simple views that render the demo HTML templates.
The actual chat functionality is handled via WebSockets and the REST API.
"""

from uuid import UUID

from django.shortcuts import get_object_or_404, render

from .models import Channel, Workspace


def index(request):
    """
    Landing page / workspace selector.

    If user is authenticated, shows their workspaces.
    Otherwise, shows login form.
    """
    workspaces = []
    if request.user.is_authenticated:
        workspaces = Workspace.objects.filter(memberships__user=request.user).order_by("name")

    return render(
        request,
        "chat/index.html",
        {
            "workspaces": workspaces,
        },
    )


def workspace(request, workspace_id: UUID):
    """
    Workspace view - shows channels and allows joining.
    """
    workspace = get_object_or_404(Workspace, id=workspace_id)

    # Check membership
    if request.user.is_authenticated:
        is_member = workspace.memberships.filter(user=request.user).exists()
    else:
        is_member = False

    channels = []
    if is_member:
        channels = (
            Channel.objects.filter(
                workspace=workspace,
                is_archived=False,
            )
            .filter(models.Q(is_private=False) | models.Q(memberships__user=request.user))
            .distinct()
            .order_by("name")
        )

    return render(
        request,
        "chat/workspace.html",
        {
            "workspace": workspace,
            "channels": channels,
            "is_member": is_member,
        },
    )


def channel(request, workspace_id: UUID, channel_id: UUID):
    """
    Channel view - main chat interface.
    """
    workspace = get_object_or_404(Workspace, id=workspace_id)
    channel = get_object_or_404(Channel, id=channel_id, workspace=workspace)

    return render(
        request,
        "chat/channel.html",
        {
            "workspace": workspace,
            "channel": channel,
        },
    )


# Import models at bottom to avoid circular imports
from django.db import models
