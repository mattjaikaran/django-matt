from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    bio = models.TextField(blank=True)
    avatar_url = models.URLField(blank=True)

    class Meta:
        db_table = "users"

    def __str__(self) -> str:
        return self.username
