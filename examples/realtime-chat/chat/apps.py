"""Chat app configuration."""

from django.apps import AppConfig


class ChatConfig(AppConfig):
    """Configuration for the chat application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "chat"
    verbose_name = "Real-Time Chat"

    def ready(self):
        """Initialize app when Django starts."""
        # Import signal handlers
        pass
