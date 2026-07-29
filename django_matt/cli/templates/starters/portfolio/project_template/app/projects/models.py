from django.db import models

from {{ project_name }}_app.core.models import BaseModel


class Project(BaseModel):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField()
    long_description = models.TextField(blank=True)
    tech_stack = models.JSONField(default=list)
    image_url = models.URLField(blank=True)
    live_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    featured = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    is_published = models.BooleanField(default=True)

    class Meta:
        db_table = "projects"
        ordering = ["order", "-created_at"]

    def __str__(self) -> str:
        return self.title
