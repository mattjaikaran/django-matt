from django.db import models

from apps.core.models import BaseModel


class ContactMessage(BaseModel):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    subject = models.CharField(max_length=255, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "contact_messages"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} <{self.email}> — {self.subject or 'no subject'}"
