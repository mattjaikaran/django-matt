"""Comment models with threading support."""

import uuid

from django.db import models


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(
        "posts.Post", on_delete=models.CASCADE, related_name="comments"
    )

    # Authenticated or anonymous
    author = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comments",
    )
    author_name = models.CharField(max_length=100, blank=True)
    author_email = models.EmailField(blank=True)

    content = models.TextField(max_length=2000)

    # Threading: a reply has a parent comment
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )

    is_approved = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Comment"
        verbose_name_plural = "Comments"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["post", "is_approved", "parent"]),
        ]

    def __str__(self) -> str:
        name = self.author.full_name if self.author else self.author_name
        return f"Comment by {name} on {self.post.title}"

    @property
    def display_name(self) -> str:
        if self.author:
            return self.author.full_name or self.author.username
        return self.author_name or "Anonymous"
