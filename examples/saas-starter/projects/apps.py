from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "projects"
    verbose_name = "Projects"

    def ready(self):
        # Import signal handlers
        import projects.signals  # noqa: F401
