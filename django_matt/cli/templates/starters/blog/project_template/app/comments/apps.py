from django.apps import AppConfig


class CommentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "{{ project_name }}_app.comments"
    label = "comments"
