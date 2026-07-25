"""Post, Tag, Category, and view-tracking models."""

import uuid

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils.text import slugify


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True)

    # Content
    content = models.TextField()
    excerpt = models.TextField(blank=True, max_length=500)
    cover_image = models.ImageField(upload_to="posts/covers/", blank=True, null=True)

    # Ownership + taxonomy
    author = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="posts",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")

    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    featured = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    # SEO
    seo_title = models.CharField(max_length=200, blank=True)
    seo_description = models.TextField(blank=True, max_length=300)

    # Analytics
    view_count = models.PositiveIntegerField(default=0)

    # Full-text search
    search_vector = SearchVectorField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Post"
        verbose_name_plural = "Posts"
        ordering = ["-published_at", "-created_at"]
        indexes = [
            GinIndex(fields=["search_vector"]),
            models.Index(fields=["status", "featured"]),
            models.Index(fields=["author", "status"]),
            models.Index(fields=["published_at"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if not self.excerpt and self.content:
            # Auto-generate excerpt from first 500 chars of content (stripped)
            import re

            text = re.sub(r"[#*`\[\]>]", "", self.content)
            self.excerpt = text[:497] + "..." if len(text) > 500 else text
        super().save(*args, **kwargs)

    @property
    def reading_time_minutes(self) -> int:
        """Estimate reading time at 200 words/minute."""
        words = len(self.content.split())
        return max(1, round(words / 200))

    @property
    def cover_image_url(self) -> str | None:
        if self.cover_image:
            return self.cover_image.url
        return None


class PostView(models.Model):
    """Deduplicated view tracking per session."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="views")
    session_key = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Post View"
        verbose_name_plural = "Post Views"
        # One view per session+post to prevent double-counting
        unique_together = ["post", "session_key"]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"View on {self.post.title}"
