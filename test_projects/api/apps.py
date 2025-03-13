from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Configuration for the api app."""
    
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
    
    def ready(self):
        """Perform initialization when the app is ready."""
        # Import signals or perform other initialization here
        pass
