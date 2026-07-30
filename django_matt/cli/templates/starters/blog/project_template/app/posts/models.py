from django.db import models


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tags"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True)
    content = models.TextField()
    excerpt = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    featured = models.BooleanField(default=False)
    author = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="posts")
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    published_at = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "posts"
        ordering = ["-published_at", "-created_at"]

    def __str__(self) -> str:
        return self.title
