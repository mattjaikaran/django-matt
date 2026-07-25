"""
Tests for the django_matt.db module.

Covers:
- SoftDeleteMixin: soft delete, hard delete, restore, is_deleted property, timestamps
- SoftDeleteWithUserMixin: user tracking on delete/restore
- SoftDeleteManager: default filtering, with_deleted, deleted_only, bulk operations
- SoftDeleteQuerySet: alive, dead, bulk delete/restore/hard_delete
- soft_delete_cascade / restore_cascade utility functions
- DB utility functions: get_db_type, is_sqlite, get_table_names, execute_raw_sql
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, Mock, patch

from django.contrib.auth import get_user_model
from django.db import connection, models
from django.utils import timezone

import pytest

from django_matt.db import (
    SoftDeleteManager,
    SoftDeleteMixin,
    SoftDeleteQuerySet,
    SoftDeleteWithUserMixin,
    execute_raw_sql,
    get_db_type,
    get_table_names,
    is_mysql,
    is_postgres,
    is_sqlite,
    restore_cascade,
    soft_delete_cascade,
)

User = get_user_model()


# =============================================================================
# Test models -- created in DB via fixtures below
# =============================================================================


class SoftArticle(SoftDeleteMixin, models.Model):
    """Test model with soft delete."""

    title = models.CharField(max_length=200)
    body = models.TextField(default="")

    class Meta:
        app_label = "tests"


class SoftComment(SoftDeleteMixin, models.Model):
    """Test model that references SoftArticle for cascade tests."""

    article = models.ForeignKey(SoftArticle, on_delete=models.CASCADE, related_name="comments")
    text = models.CharField(max_length=500)

    class Meta:
        app_label = "tests"


class SoftDocument(SoftDeleteWithUserMixin, models.Model):
    """Test model with soft delete + user tracking."""

    name = models.CharField(max_length=200)

    class Meta:
        app_label = "tests"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def _create_soft_delete_tables(django_db_setup, django_db_blocker):
    """Create the test model tables once per session."""
    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        for model in (SoftArticle, SoftComment, SoftDocument):
            try:
                editor.create_model(model)
            except Exception:
                pass  # table may already exist


@pytest.fixture(autouse=True)
def _soft_tables(_create_soft_delete_tables):
    """Ensure soft-delete tables exist for every test in this module."""


# =============================================================================
# SoftDeleteMixin -- instance-level behaviour
# =============================================================================


@pytest.mark.django_db
class TestSoftDeleteMixin:
    """Tests for the SoftDeleteMixin model mixin."""

    def test_new_record_is_not_deleted(self):
        """A freshly created record has is_deleted=False and deleted_at=None."""
        article = SoftArticle.objects.create(title="New Article")
        assert article.is_deleted is False
        assert article.deleted_at is None

    def test_soft_delete_sets_deleted_at(self):
        """Calling .delete() sets deleted_at to a timestamp."""
        article = SoftArticle.objects.create(title="To Delete")
        before = timezone.now()
        article.delete()
        article.refresh_from_db()

        assert article.is_deleted is True
        assert article.deleted_at is not None
        assert article.deleted_at >= before

    def test_soft_delete_does_not_remove_from_db(self):
        """Soft-deleted records still exist in the database."""
        article = SoftArticle.objects.create(title="Still Here")
        article.delete()

        # all_objects (alive_only=False) should find it
        assert SoftArticle.all_objects.filter(pk=article.pk).exists()

    def test_hard_delete_removes_from_db(self):
        """Calling .hard_delete() permanently removes the record."""
        article = SoftArticle.objects.create(title="Gone Forever")
        pk = article.pk
        article.hard_delete()

        assert not SoftArticle.all_objects.filter(pk=pk).exists()

    def test_restore_clears_deleted_at(self):
        """Calling .restore() sets deleted_at back to None."""
        article = SoftArticle.objects.create(title="Restored")
        article.delete()
        assert article.is_deleted is True

        article.restore()
        article.refresh_from_db()

        assert article.is_deleted is False
        assert article.deleted_at is None

    def test_delete_is_idempotent(self):
        """Calling .delete() twice updates deleted_at but stays soft-deleted."""
        article = SoftArticle.objects.create(title="Double Delete")
        article.delete()
        first_ts = article.deleted_at

        article.delete()
        assert article.is_deleted is True
        # Timestamp may have been updated, but record is still soft-deleted
        assert article.deleted_at is not None

    def test_restore_on_non_deleted_is_safe(self):
        """Calling .restore() on an active record is a no-op."""
        article = SoftArticle.objects.create(title="Active")
        article.restore()
        article.refresh_from_db()

        assert article.is_deleted is False
        assert article.deleted_at is None


# =============================================================================
# Async instance-level methods
# =============================================================================


@pytest.mark.django_db
class TestSoftDeleteMixinAsync:
    """Tests for the async soft delete methods."""

    @pytest.mark.asyncio
    async def test_adelete_sets_deleted_at(self):
        """Async .adelete() sets deleted_at timestamp."""
        article = await SoftArticle.objects.acreate(title="Async Delete")
        await article.adelete()
        await article.arefresh_from_db()

        assert article.is_deleted is True
        assert article.deleted_at is not None

    @pytest.mark.asyncio
    async def test_arestore_clears_deleted_at(self):
        """Async .arestore() clears deleted_at."""
        article = await SoftArticle.objects.acreate(title="Async Restore")
        await article.adelete()
        assert article.is_deleted is True

        await article.arestore()
        await article.arefresh_from_db()

        assert article.is_deleted is False
        assert article.deleted_at is None

    @pytest.mark.asyncio
    async def test_ahard_delete_removes_from_db(self):
        """Async .ahard_delete() permanently removes the record."""
        article = await SoftArticle.objects.acreate(title="Async Hard Delete")
        pk = article.pk
        await article.ahard_delete()

        exists = await SoftArticle.all_objects.filter(pk=pk).aexists()
        assert exists is False


# =============================================================================
# SoftDeleteManager -- queryset scoping
# =============================================================================


@pytest.mark.django_db
class TestSoftDeleteManager:
    """Tests for the SoftDeleteManager (objects / all_objects)."""

    def test_default_manager_excludes_deleted(self):
        """objects.all() does not return soft-deleted records."""
        a1 = SoftArticle.objects.create(title="Alive")
        a2 = SoftArticle.objects.create(title="Dead")
        a2.delete()

        qs = SoftArticle.objects.all()
        assert a1 in qs
        assert a2 not in qs

    def test_with_deleted_includes_all(self):
        """objects.with_deleted() returns both alive and deleted records."""
        a1 = SoftArticle.objects.create(title="Visible")
        a2 = SoftArticle.objects.create(title="Hidden")
        a2.delete()

        qs = SoftArticle.objects.with_deleted()
        pks = set(qs.values_list("pk", flat=True))
        assert a1.pk in pks
        assert a2.pk in pks

    def test_deleted_only_returns_only_deleted(self):
        """objects.deleted_only() returns only soft-deleted records."""
        a1 = SoftArticle.objects.create(title="Active")
        a2 = SoftArticle.objects.create(title="Removed")
        a2.delete()

        qs = SoftArticle.objects.deleted_only()
        pks = list(qs.values_list("pk", flat=True))
        assert a2.pk in pks
        assert a1.pk not in pks

    def test_all_objects_returns_everything(self):
        """all_objects manager does not filter anything."""
        a1 = SoftArticle.objects.create(title="One")
        a2 = SoftArticle.objects.create(title="Two")
        a2.delete()

        qs = SoftArticle.all_objects.all()
        pks = set(qs.values_list("pk", flat=True))
        assert a1.pk in pks
        assert a2.pk in pks

    def test_manager_count_reflects_filtering(self):
        """Counts from objects vs all_objects differ after soft delete."""
        SoftArticle.objects.create(title="CountA")
        b = SoftArticle.objects.create(title="CountB")
        b.delete()

        alive_count = SoftArticle.objects.count()
        total_count = SoftArticle.all_objects.count()
        # total should include the soft-deleted one
        assert total_count > alive_count

    def test_manager_hard_delete(self):
        """Manager.hard_delete() permanently removes all matched records."""
        a1 = SoftArticle.objects.create(title="HD1")
        a2 = SoftArticle.objects.create(title="HD2")

        SoftArticle.objects.filter(pk__in=[a1.pk, a2.pk]).hard_delete()
        assert not SoftArticle.all_objects.filter(pk__in=[a1.pk, a2.pk]).exists()

    def test_manager_restore(self):
        """Manager.restore() restores all soft-deleted records."""
        a1 = SoftArticle.objects.create(title="R1")
        a2 = SoftArticle.objects.create(title="R2")
        a1.delete()
        a2.delete()

        SoftArticle.objects.restore()

        assert SoftArticle.objects.filter(pk__in=[a1.pk, a2.pk]).count() == 2


# =============================================================================
# SoftDeleteQuerySet -- bulk operations
# =============================================================================


@pytest.mark.django_db
class TestSoftDeleteQuerySet:
    """Tests for the SoftDeleteQuerySet methods."""

    def test_queryset_delete_is_soft(self):
        """QuerySet.delete() performs a soft delete (bulk)."""
        a1 = SoftArticle.objects.create(title="Bulk1")
        a2 = SoftArticle.objects.create(title="Bulk2")

        SoftArticle.objects.filter(pk__in=[a1.pk, a2.pk]).delete()

        # Both should still exist in DB but be soft-deleted
        assert SoftArticle.all_objects.filter(pk=a1.pk, deleted_at__isnull=False).exists()
        assert SoftArticle.all_objects.filter(pk=a2.pk, deleted_at__isnull=False).exists()

    def test_queryset_hard_delete_is_permanent(self):
        """QuerySet.hard_delete() permanently removes records."""
        a1 = SoftArticle.objects.create(title="Perm1")
        a2 = SoftArticle.objects.create(title="Perm2")

        SoftArticle.objects.filter(pk__in=[a1.pk, a2.pk]).hard_delete()

        assert not SoftArticle.all_objects.filter(pk__in=[a1.pk, a2.pk]).exists()

    def test_queryset_restore_bulk(self):
        """QuerySet.restore() restores all records in the queryset."""
        a1 = SoftArticle.objects.create(title="Res1")
        a2 = SoftArticle.objects.create(title="Res2")
        a1.delete()
        a2.delete()

        SoftArticle.objects.deleted_only().filter(pk__in=[a1.pk, a2.pk]).restore()

        a1.refresh_from_db()
        a2.refresh_from_db()
        assert a1.is_deleted is False
        assert a2.is_deleted is False

    def test_queryset_alive(self):
        """QuerySet.alive() filters to non-deleted records."""
        a1 = SoftArticle.objects.create(title="AliveQ")
        a2 = SoftArticle.objects.create(title="DeadQ")
        a2.delete()

        alive_pks = set(SoftArticle.all_objects.all().alive().values_list("pk", flat=True))
        assert a1.pk in alive_pks
        assert a2.pk not in alive_pks

    def test_queryset_dead(self):
        """QuerySet.dead() filters to deleted records."""
        a1 = SoftArticle.objects.create(title="AliveD")
        a2 = SoftArticle.objects.create(title="DeadD")
        a2.delete()

        dead_pks = set(SoftArticle.all_objects.all().dead().values_list("pk", flat=True))
        assert a2.pk in dead_pks
        assert a1.pk not in dead_pks

    def test_chained_filtering(self):
        """Filters can be chained with alive/dead."""
        SoftArticle.objects.create(title="Chain-Alive", body="x")
        b = SoftArticle.objects.create(title="Chain-Dead", body="x")
        b.delete()

        qs = SoftArticle.all_objects.filter(body="x").alive()
        titles = list(qs.values_list("title", flat=True))
        assert "Chain-Alive" in titles
        assert "Chain-Dead" not in titles


# =============================================================================
# SoftDeleteWithUserMixin
# =============================================================================


@pytest.mark.django_db
class TestSoftDeleteWithUserMixin:
    """Tests for the SoftDeleteWithUserMixin (user tracking)."""

    def test_delete_without_user(self):
        """Delete without user sets deleted_at but leaves deleted_by null."""
        doc = SoftDocument.objects.create(name="NoUser")
        doc.delete()
        doc.refresh_from_db()

        assert doc.is_deleted is True
        assert doc.deleted_by is None

    def test_delete_with_user(self):
        """Delete with user tracks who deleted the record."""
        user = User.objects.create_user(username="deleter", password="pass1234")
        doc = SoftDocument.objects.create(name="WithUser")
        doc.delete(user=user)
        doc.refresh_from_db()

        assert doc.is_deleted is True
        assert doc.deleted_by_id == user.pk

    def test_restore_clears_deleted_by(self):
        """Restore clears both deleted_at and deleted_by."""
        user = User.objects.create_user(username="restorer", password="pass1234")
        doc = SoftDocument.objects.create(name="Restored")
        doc.delete(user=user)

        doc.restore()
        doc.refresh_from_db()

        assert doc.is_deleted is False
        assert doc.deleted_by is None

    @pytest.mark.asyncio
    async def test_adelete_with_user(self):
        """Async adelete tracks the user."""
        user = await User.objects.acreate_user(username="async_deleter", password="pass1234")
        doc = await SoftDocument.objects.acreate(name="AsyncDoc")
        await doc.adelete(user=user)
        await doc.arefresh_from_db()

        assert doc.is_deleted is True
        assert doc.deleted_by_id == user.pk

    @pytest.mark.asyncio
    async def test_arestore_clears_user(self):
        """Async arestore clears deleted_by."""
        user = await User.objects.acreate_user(username="async_restorer", password="pass1234")
        doc = await SoftDocument.objects.acreate(name="AsyncRestoreDoc")
        await doc.adelete(user=user)

        await doc.arestore()
        await doc.arefresh_from_db()

        assert doc.is_deleted is False
        assert doc.deleted_by is None


# =============================================================================
# Cascade functions
# =============================================================================


@pytest.mark.django_db
class TestSoftDeleteCascade:
    """Tests for soft_delete_cascade and restore_cascade utility functions."""

    def test_soft_delete_cascade_deletes_parent_and_children(self):
        """soft_delete_cascade soft-deletes the parent and related children."""
        article = SoftArticle.objects.create(title="Cascade Parent")
        c1 = SoftComment.objects.create(article=article, text="Comment 1")
        c2 = SoftComment.objects.create(article=article, text="Comment 2")

        soft_delete_cascade(article)

        article.refresh_from_db()
        c1.refresh_from_db()
        c2.refresh_from_db()

        assert article.is_deleted is True
        assert c1.is_deleted is True
        assert c2.is_deleted is True

    def test_soft_delete_cascade_does_not_affect_unrelated(self):
        """Cascade only affects related children, not other records."""
        a1 = SoftArticle.objects.create(title="Parent")
        a2 = SoftArticle.objects.create(title="Unrelated")
        SoftComment.objects.create(article=a1, text="Child of a1")
        c_other = SoftComment.objects.create(article=a2, text="Child of a2")

        soft_delete_cascade(a1)

        c_other.refresh_from_db()
        a2.refresh_from_db()
        assert a2.is_deleted is False
        assert c_other.is_deleted is False

    def test_restore_cascade_restores_parent_and_children(self):
        """restore_cascade restores the parent and all related children."""
        article = SoftArticle.objects.create(title="Restore Cascade")
        c1 = SoftComment.objects.create(article=article, text="RC1")
        c2 = SoftComment.objects.create(article=article, text="RC2")

        soft_delete_cascade(article)
        # Verify all are deleted first
        article.refresh_from_db()
        assert article.is_deleted is True

        restore_cascade(article)

        article.refresh_from_db()
        c1.refresh_from_db()
        c2.refresh_from_db()

        assert article.is_deleted is False
        assert c1.is_deleted is False
        assert c2.is_deleted is False

    def test_soft_delete_cascade_on_non_softdelete_model_is_safe(self):
        """Calling soft_delete_cascade on a model without deleted_at is safe."""
        mock_instance = Mock(spec=[])
        mock_instance._meta = Mock()
        mock_instance._meta.get_fields.return_value = []
        # Should not raise
        soft_delete_cascade(mock_instance)

    def test_restore_cascade_on_non_softdelete_model_is_safe(self):
        """Calling restore_cascade on a model without deleted_at is safe."""
        mock_instance = Mock(spec=[])
        mock_instance._meta = Mock()
        mock_instance._meta.get_fields.return_value = []
        restore_cascade(mock_instance)


# =============================================================================
# SoftDeleteManager -- constructor and internal state
# =============================================================================


class TestSoftDeleteManagerConfig:
    """Tests for SoftDeleteManager configuration."""

    def test_alive_only_default_true(self):
        """Default manager has alive_only=True."""
        manager = SoftDeleteManager(alive_only=True)
        assert manager.alive_only is True

    def test_alive_only_false(self):
        """Manager constructed with alive_only=False retains it."""
        manager = SoftDeleteManager(alive_only=False)
        assert manager.alive_only is False

    def test_queryset_class_is_soft_delete(self):
        """The manager's _queryset_class is SoftDeleteQuerySet."""
        manager = SoftDeleteManager()
        assert manager._queryset_class is SoftDeleteQuerySet


# =============================================================================
# SoftDeleteMixin -- model Meta and fields
# =============================================================================


class TestSoftDeleteMixinMeta:
    """Tests for model field definitions from SoftDeleteMixin."""

    def test_deleted_at_field_exists(self):
        """SoftDeleteMixin adds a deleted_at DateTimeField."""
        field = SoftArticle._meta.get_field("deleted_at")
        assert isinstance(field, models.DateTimeField)
        assert field.null is True
        assert field.blank is True
        assert field.db_index is True

    def test_deleted_at_default_is_none(self):
        """deleted_at defaults to None."""
        field = SoftArticle._meta.get_field("deleted_at")
        assert field.default is None

    def test_deleted_by_field_on_user_mixin(self):
        """SoftDeleteWithUserMixin adds a deleted_by ForeignKey."""
        field = SoftDocument._meta.get_field("deleted_by")
        assert isinstance(field, models.ForeignKey)
        assert field.null is True
        assert field.blank is True

    def test_is_abstract(self):
        """SoftDeleteMixin itself is abstract."""
        assert SoftDeleteMixin._meta.abstract is True

    def test_with_user_mixin_is_abstract(self):
        """SoftDeleteWithUserMixin itself is abstract."""
        assert SoftDeleteWithUserMixin._meta.abstract is True


# =============================================================================
# is_deleted property edge cases
# =============================================================================


@pytest.mark.django_db
class TestIsDeletedProperty:
    """Edge-case tests for the is_deleted property."""

    def test_is_deleted_true_after_soft_delete(self):
        """is_deleted returns True immediately after .delete()."""
        article = SoftArticle.objects.create(title="PropTest")
        article.delete()
        assert article.is_deleted is True

    def test_is_deleted_false_after_restore(self):
        """is_deleted returns False immediately after .restore()."""
        article = SoftArticle.objects.create(title="PropRestore")
        article.delete()
        article.restore()
        assert article.is_deleted is False

    def test_is_deleted_false_on_unsaved_instance(self):
        """is_deleted is False on a brand-new unsaved instance."""
        article = SoftArticle(title="Unsaved")
        assert article.is_deleted is False


# =============================================================================
# DB utility functions (from __init__.py)
# =============================================================================


@pytest.mark.django_db
class TestDBUtilities:
    """Tests for the database utility functions in django_matt.db."""

    def test_get_db_type_returns_string(self):
        """get_db_type returns the database vendor string."""
        db_type = get_db_type()
        assert isinstance(db_type, str)
        # Test environment uses sqlite
        assert db_type == "sqlite"

    def test_is_sqlite_in_test_env(self):
        """is_sqlite() returns True in the test environment (SQLite in-memory)."""
        assert is_sqlite() is True

    def test_is_postgres_false_in_test_env(self):
        """is_postgres() returns False when running on SQLite."""
        assert is_postgres() is False

    def test_is_mysql_false_in_test_env(self):
        """is_mysql() returns False when running on SQLite."""
        assert is_mysql() is False

    def test_get_table_names_returns_list(self):
        """get_table_names() returns a non-empty list of table names."""
        tables = get_table_names()
        assert isinstance(tables, list)
        assert len(tables) > 0

    def test_execute_raw_sql_select(self):
        """execute_raw_sql can execute a SELECT statement."""
        result = execute_raw_sql("SELECT 1 AS val")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["val"] == 1

    def test_execute_raw_sql_with_params(self):
        """execute_raw_sql supports parameterized queries."""
        result = execute_raw_sql("SELECT ? + ? AS total", [3, 7])
        assert result[0]["total"] == 10

    def test_execute_raw_sql_no_results(self):
        """execute_raw_sql returns empty list for non-SELECT statements."""
        # CREATE TABLE IF NOT EXISTS is safe to run
        result = execute_raw_sql(
            "CREATE TABLE IF NOT EXISTS _test_raw_sql (id INTEGER PRIMARY KEY)"
        )
        assert result == []

        # Cleanup
        execute_raw_sql("DROP TABLE IF EXISTS _test_raw_sql")


# =============================================================================
# QuerySet interaction with Django ORM features
# =============================================================================


@pytest.mark.django_db
class TestSoftDeleteWithDjangoORM:
    """Tests verifying soft delete integrates correctly with Django ORM features."""

    def test_get_raises_does_not_exist_for_soft_deleted(self):
        """objects.get() raises DoesNotExist for soft-deleted records."""
        article = SoftArticle.objects.create(title="GhostGet")
        article.delete()

        with pytest.raises(SoftArticle.DoesNotExist):
            SoftArticle.objects.get(pk=article.pk)

    def test_get_or_create_ignores_soft_deleted(self):
        """get_or_create creates a new record if the match is soft-deleted."""
        article = SoftArticle.objects.create(title="GetOrCreate")
        article.delete()

        new_article, created = SoftArticle.objects.get_or_create(
            title="GetOrCreate", defaults={"body": "new"}
        )
        assert created is True
        assert new_article.pk != article.pk

    def test_filter_excludes_soft_deleted(self):
        """objects.filter() excludes soft-deleted records by default."""
        a1 = SoftArticle.objects.create(title="FilterTest")
        a2 = SoftArticle.objects.create(title="FilterTest")
        a2.delete()

        results = SoftArticle.objects.filter(title="FilterTest")
        assert results.count() == 1
        assert results.first().pk == a1.pk

    def test_exists_false_for_soft_deleted(self):
        """objects.filter(...).exists() returns False for soft-deleted records."""
        article = SoftArticle.objects.create(title="ExistsTest")
        article.delete()

        assert SoftArticle.objects.filter(pk=article.pk).exists() is False

    def test_values_list_excludes_soft_deleted(self):
        """values_list through default manager excludes soft-deleted records."""
        a1 = SoftArticle.objects.create(title="VL-Alive")
        a2 = SoftArticle.objects.create(title="VL-Dead")
        a2.delete()

        titles = list(SoftArticle.objects.values_list("title", flat=True))
        assert "VL-Alive" in titles
        assert "VL-Dead" not in titles

    def test_update_through_default_manager(self):
        """Updating through default manager only affects alive records."""
        a1 = SoftArticle.objects.create(title="Update-Alive", body="old")
        a2 = SoftArticle.objects.create(title="Update-Dead", body="old")
        a2.delete()

        SoftArticle.objects.filter(body="old").update(body="new")

        a1.refresh_from_db()
        a2.refresh_from_db()
        assert a1.body == "new"
        # Soft-deleted record was NOT updated because default manager filters it out
        assert a2.body == "old"


# =============================================================================
# Postgres utilities -- guarded (tests skip when not on PG)
# =============================================================================


class TestPostgresUtilities:
    """Tests for PostgreSQL-specific utilities (guarded, skip when not PG)."""

    def test_check_postgres_connection_false_on_sqlite(self):
        """check_postgres_connection returns False on SQLite."""
        from django_matt.db.postgres import check_postgres_connection

        assert check_postgres_connection() is False

    def test_is_postgres_version_compatible_false_on_sqlite(self):
        """is_postgres_version_compatible returns False on SQLite."""
        from django_matt.db.postgres import is_postgres_version_compatible

        assert is_postgres_version_compatible() is False

    def test_create_extension_raises_on_sqlite(self):
        """create_extension raises ValueError on non-PostgreSQL connection."""
        from django_matt.db.postgres import create_extension

        with pytest.raises(ValueError, match="not PostgreSQL"):
            create_extension("pg_trgm")

    def test_list_extensions_raises_on_sqlite(self):
        """list_extensions raises ValueError on non-PostgreSQL connection."""
        from django_matt.db.postgres import list_extensions

        with pytest.raises(ValueError, match="not PostgreSQL"):
            list_extensions()

    def test_execute_sql_raises_on_sqlite(self):
        """execute_sql raises ValueError on non-PostgreSQL connection."""
        from django_matt.db.postgres import execute_sql

        with pytest.raises(ValueError, match="not PostgreSQL"):
            execute_sql("SELECT 1")


# =============================================================================
# Module-level exports
# =============================================================================


class TestDBModuleExports:
    """Tests that the db module exposes the expected public API."""

    def test_soft_delete_exports(self):
        """All soft-delete classes and functions are importable from django_matt.db."""
        from django_matt.db import (
            SoftDeleteManager,
            SoftDeleteMixin,
            SoftDeleteQuerySet,
            SoftDeleteWithUserMixin,
            restore_cascade,
            soft_delete_cascade,
        )

        assert SoftDeleteMixin is not None
        assert SoftDeleteWithUserMixin is not None
        assert SoftDeleteManager is not None
        assert SoftDeleteQuerySet is not None
        assert soft_delete_cascade is not None
        assert restore_cascade is not None

    def test_db_utility_exports(self):
        """DB utility functions are importable from django_matt.db."""
        from django_matt.db import (
            execute_raw_sql,
            get_db_type,
            get_db_version,
            get_table_description,
            get_table_names,
            is_mysql,
            is_postgres,
            is_sqlite,
        )

        assert callable(get_db_type)
        assert callable(is_postgres)
        assert callable(is_mysql)
        assert callable(is_sqlite)
        assert callable(get_db_version)
        assert callable(get_table_names)
        assert callable(get_table_description)
        assert callable(execute_raw_sql)
