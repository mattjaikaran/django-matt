from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model with email as primary identifier."""

    email = models.EmailField(unique=True)
    avatar_url = models.URLField(blank=True, null=True)
    bio = models.TextField(blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "users"

    def __str__(self) -> str:
        return self.email
