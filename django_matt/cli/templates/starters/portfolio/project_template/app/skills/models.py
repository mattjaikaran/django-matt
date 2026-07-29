from django.db import models

from {{ project_name }}_app.core.models import BaseModel


class SkillCategory(models.TextChoices):
    FRONTEND = "frontend", "Frontend"
    BACKEND = "backend", "Backend"
    DEVOPS = "devops", "DevOps"
    DATABASE = "database", "Database"
    MOBILE = "mobile", "Mobile"
    OTHER = "other", "Other"


class Skill(BaseModel):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=SkillCategory.choices)
    level = models.IntegerField(default=3)
    icon = models.CharField(max_length=50, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        db_table = "skills"
        ordering = ["category", "order", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.category})"
