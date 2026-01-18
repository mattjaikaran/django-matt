"""
Soft delete functionality for Django models.

Provides mixins and managers for soft-deleting records instead of
permanently removing them from the database.

Usage:
    from django_matt.db import SoftDeleteMixin

    class Article(SoftDeleteMixin, models.Model):
        title = models.CharField(max_length=200)
        content = models.TextField()

    # Soft delete (sets deleted_at timestamp)
    article.delete()

    # Hard delete (permanently removes)
    article.hard_delete()

    # Restore a soft-deleted record
    article.restore()

    # Query only active records (default)
    Article.objects.all()  # excludes deleted

    # Query including deleted records
    Article.objects.with_deleted().all()

    # Query only deleted records
    Article.objects.deleted_only().all()

    # Bulk operations
    Article.objects.filter(author=user).delete()  # soft delete all
    Article.objects.filter(author=user).hard_delete()  # hard delete all
    Article.objects.deleted_only().filter(author=user).restore()  # restore all
"""

from django.db import models
from django.db.models.query import QuerySet
from django.utils import timezone


class SoftDeleteQuerySet(QuerySet):
    """
    QuerySet that supports soft delete operations.

    By default, excludes soft-deleted records.
    Use `with_deleted()` to include them.
    """

    def delete(self):
        """Soft delete all records in the queryset."""
        return self.update(deleted_at=timezone.now())

    def hard_delete(self):
        """Permanently delete all records in the queryset."""
        return super().delete()

    def restore(self):
        """Restore all soft-deleted records in the queryset."""
        return self.update(deleted_at=None)

    def alive(self):
        """Filter to only non-deleted records."""
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        """Filter to only deleted records."""
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager):
    """
    Manager that excludes soft-deleted records by default.

    Methods:
        all() - Returns only non-deleted records
        with_deleted() - Returns all records including deleted
        deleted_only() - Returns only deleted records
    """

    _queryset_class = SoftDeleteQuerySet

    def __init__(self, *args, alive_only: bool = True, **kwargs):
        self.alive_only = alive_only
        super().__init__(*args, **kwargs)

    def get_queryset(self) -> SoftDeleteQuerySet:
        """Get base queryset, optionally filtering out deleted records."""
        qs = self._queryset_class(self.model, using=self._db)
        if self.alive_only:
            return qs.filter(deleted_at__isnull=True)
        return qs

    def with_deleted(self) -> SoftDeleteQuerySet:
        """Return queryset including soft-deleted records."""
        return self._queryset_class(self.model, using=self._db)

    def deleted_only(self) -> SoftDeleteQuerySet:
        """Return queryset with only soft-deleted records."""
        return self._queryset_class(self.model, using=self._db).filter(deleted_at__isnull=False)

    def hard_delete(self):
        """Hard delete all records in the queryset."""
        return self.get_queryset().hard_delete()

    def restore(self):
        """Restore all soft-deleted records."""
        return self.deleted_only().restore()


class SoftDeleteMixin(models.Model):
    """
    Mixin that adds soft delete functionality to a model.

    Adds:
        - deleted_at: Timestamp when the record was deleted (null = not deleted)
        - is_deleted: Property that returns True if record is deleted
        - delete(): Soft deletes the record
        - hard_delete(): Permanently deletes the record
        - restore(): Restores a soft-deleted record

    The default manager (objects) excludes deleted records.
    Use `Model.all_objects` or `Model.objects.with_deleted()` to include them.

    Example:
        class Post(SoftDeleteMixin, models.Model):
            title = models.CharField(max_length=200)
            author = models.ForeignKey(User, on_delete=models.CASCADE)

        # Create and soft delete
        post = Post.objects.create(title="Hello", author=user)
        post.delete()  # Sets deleted_at, doesn't remove from DB

        # Post is now hidden from default queries
        Post.objects.count()  # 0
        Post.objects.with_deleted().count()  # 1
        Post.objects.deleted_only().count()  # 1

        # Restore it
        post.restore()
        Post.objects.count()  # 1

        # Hard delete (permanent)
        post.hard_delete()  # Actually removes from DB
    """

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        db_index=True,
        help_text="Timestamp when the record was soft-deleted",
    )

    # Default manager excludes deleted records
    objects = SoftDeleteManager(alive_only=True)

    # Manager that includes all records
    all_objects = SoftDeleteManager(alive_only=False)

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        """Check if this record is soft-deleted."""
        return self.deleted_at is not None

    def delete(self, using=None, keep_parents=False):
        """
        Soft delete this record.

        Sets deleted_at to current timestamp instead of removing from database.

        Args:
            using: Database alias to use
            keep_parents: Ignored (for compatibility with Django's delete())
        """
        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=["deleted_at"])

    async def adelete(self, using=None, keep_parents=False):
        """Async version of soft delete."""
        self.deleted_at = timezone.now()
        await self.asave(using=using, update_fields=["deleted_at"])

    def hard_delete(self, using=None, keep_parents=False):
        """
        Permanently delete this record from the database.

        Args:
            using: Database alias to use
            keep_parents: Whether to keep parent records in multi-table inheritance
        """
        return super().delete(using=using, keep_parents=keep_parents)

    async def ahard_delete(self, using=None, keep_parents=False):
        """Async version of hard delete."""
        return await super().adelete(using=using, keep_parents=keep_parents)

    def restore(self, using=None):
        """
        Restore this soft-deleted record.

        Sets deleted_at to None.

        Args:
            using: Database alias to use
        """
        self.deleted_at = None
        self.save(using=using, update_fields=["deleted_at"])

    async def arestore(self, using=None):
        """Async version of restore."""
        self.deleted_at = None
        await self.asave(using=using, update_fields=["deleted_at"])


class SoftDeleteWithUserMixin(SoftDeleteMixin):
    """
    Soft delete mixin that also tracks who deleted the record.

    Adds:
        - deleted_by: ForeignKey to the user who deleted the record

    Example:
        class Document(SoftDeleteWithUserMixin, models.Model):
            title = models.CharField(max_length=200)

        # Delete with user tracking
        document.delete(user=request.user)

        # Check who deleted it
        print(document.deleted_by)  # User instance
    """

    deleted_by = models.ForeignKey(
        "auth.User",  # Will be resolved at runtime
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_deleted",
        help_text="User who soft-deleted this record",
    )

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, user=None):
        """
        Soft delete this record, optionally tracking the user.

        Args:
            using: Database alias to use
            keep_parents: Ignored
            user: User who is deleting the record
        """
        self.deleted_at = timezone.now()
        if user is not None:
            self.deleted_by = user
        self.save(using=using, update_fields=["deleted_at", "deleted_by"])

    async def adelete(self, using=None, keep_parents=False, user=None):
        """Async version of soft delete with user tracking."""
        self.deleted_at = timezone.now()
        if user is not None:
            self.deleted_by = user
        await self.asave(using=using, update_fields=["deleted_at", "deleted_by"])

    def restore(self, using=None):
        """Restore and clear deleted_by."""
        self.deleted_at = None
        self.deleted_by = None
        self.save(using=using, update_fields=["deleted_at", "deleted_by"])

    async def arestore(self, using=None):
        """Async version of restore."""
        self.deleted_at = None
        self.deleted_by = None
        await self.asave(using=using, update_fields=["deleted_at", "deleted_by"])


# Utility functions


def soft_delete_cascade(instance, using=None):
    """
    Soft delete an instance and all related objects that have SoftDeleteMixin.

    This is a simple implementation - for complex cascades, consider
    using Django signals or custom logic.

    Args:
        instance: Model instance to soft delete
        using: Database alias

    Example:
        # Soft delete user and all their posts
        soft_delete_cascade(user)
    """

    now = timezone.now()

    # First, soft delete the instance itself
    if hasattr(instance, "deleted_at"):
        instance.deleted_at = now
        instance.save(using=using, update_fields=["deleted_at"])

    # Then find and soft delete related objects
    for field in instance._meta.get_fields():
        if hasattr(field, "related_model") and field.related_model:
            related_model = field.related_model
            # Check if related model has soft delete
            if hasattr(related_model, "deleted_at"):
                # Get the related manager
                if hasattr(field, "get_accessor_name"):
                    accessor = field.get_accessor_name()
                    if hasattr(instance, accessor):
                        related_manager = getattr(instance, accessor)
                        if hasattr(related_manager, "update"):
                            related_manager.update(deleted_at=now)


def restore_cascade(instance, using=None):
    """
    Restore an instance and all related soft-deleted objects.

    Args:
        instance: Model instance to restore
        using: Database alias
    """
    # Restore the instance
    if hasattr(instance, "deleted_at"):
        instance.deleted_at = None
        instance.save(using=using, update_fields=["deleted_at"])

    # Restore related objects
    for field in instance._meta.get_fields():
        if hasattr(field, "related_model") and field.related_model:
            related_model = field.related_model
            if hasattr(related_model, "deleted_at"):
                if hasattr(field, "get_accessor_name"):
                    accessor = field.get_accessor_name()
                    if hasattr(instance, accessor):
                        related_manager = getattr(instance, accessor)
                        if hasattr(related_manager, "update"):
                            related_manager.update(deleted_at=None)
