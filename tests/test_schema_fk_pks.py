"""Tests for ModelSchema model_fk_use_pks=True (Enhancement 2.6)."""

import uuid

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
        ],
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    )
    django.setup()

from django.db import models

import pytest

from django_matt.core.schema import ModelSchema

# ---- Test models ----


class Author(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "testapp"


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    label = models.CharField(max_length=50)

    class Meta:
        app_label = "testapp"


class Article(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    editor = models.ForeignKey(
        Author, on_delete=models.SET_NULL, null=True, related_name="edited_articles"
    )

    class Meta:
        app_label = "testapp"


class Profile(models.Model):
    user = models.OneToOneField(Author, on_delete=models.CASCADE)
    bio = models.TextField(default="")

    class Meta:
        app_label = "testapp"


class UUIDFKModel(models.Model):
    ref = models.ForeignKey(UUIDModel, on_delete=models.CASCADE)

    class Meta:
        app_label = "testapp"


# ---- Tests ----


class TestFKUsePKsDisabledByDefault:
    """Default behavior: FK fields keep their original name."""

    def test_default_fk_field_name(self):
        class ArticleSchema(ModelSchema):
            class Config:
                model = Article
                include = "__all__"

        assert "author" in ArticleSchema.model_fields
        assert "author_id" not in ArticleSchema.model_fields

    def test_default_one_to_one_field_name(self):
        class ProfileSchema(ModelSchema):
            class Config:
                model = Profile
                include = "__all__"

        assert "user" in ProfileSchema.model_fields
        assert "user_id" not in ProfileSchema.model_fields


class TestFKUsePKsEnabled:
    """When model_fk_use_pks=True, FK fields map to _id columns."""

    def test_fk_renamed_to_id(self):
        class ArticleSchema(ModelSchema):
            class Config:
                model = Article
                include = "__all__"
                model_fk_use_pks = True

        assert "author_id" in ArticleSchema.model_fields
        assert "author" not in ArticleSchema.model_fields
        assert "editor_id" in ArticleSchema.model_fields
        assert "editor" not in ArticleSchema.model_fields
        # Non-FK fields unchanged
        assert "title" in ArticleSchema.model_fields
        assert "id" in ArticleSchema.model_fields

    def test_one_to_one_renamed_to_id(self):
        class ProfileSchema(ModelSchema):
            class Config:
                model = Profile
                include = "__all__"
                model_fk_use_pks = True

        assert "user_id" in ProfileSchema.model_fields
        assert "user" not in ProfileSchema.model_fields

    def test_fk_type_is_int(self):
        class ArticleSchema(ModelSchema):
            class Config:
                model = Article
                include = "__all__"
                model_fk_use_pks = True

        # author_id is required (not nullable), should be int
        field = ArticleSchema.model_fields["author_id"]
        assert field.annotation is int or field.annotation == int

    def test_nullable_fk_is_optional(self):
        class ArticleSchema(ModelSchema):
            class Config:
                model = Article
                include = "__all__"
                model_fk_use_pks = True

        # editor is nullable FK — editor_id should be Optional[int]
        import typing

        field_type = ArticleSchema.__annotations__["editor_id"]
        # Should be Optional[int]
        args = typing.get_args(field_type)
        assert int in args
        assert type(None) in args

    def test_uuid_pk_type(self):
        """FK to a model with UUID PK should produce uuid.UUID type."""

        class UUIDFKSchema(ModelSchema):
            class Config:
                model = UUIDFKModel
                include = "__all__"
                model_fk_use_pks = True

        assert "ref_id" in UUIDFKSchema.model_fields
        assert UUIDFKSchema.__annotations__["ref_id"] is uuid.UUID

    def test_explicit_include_with_id_name(self):
        """Users can include fields by their _id name."""

        class ArticleSchema(ModelSchema):
            class Config:
                model = Article
                include = ["id", "title", "author_id"]
                model_fk_use_pks = True

        assert "author_id" in ArticleSchema.model_fields
        assert "editor_id" not in ArticleSchema.model_fields

    def test_explicit_include_with_original_name(self):
        """Users can also include FK fields by their original name."""

        class ArticleSchema(ModelSchema):
            class Config:
                model = Article
                include = ["id", "title", "author"]
                model_fk_use_pks = True

        assert "author_id" in ArticleSchema.model_fields

    def test_exclude_fk_by_id_name(self):
        """Excluding by _id name should work."""

        class ArticleSchema(ModelSchema):
            class Config:
                model = Article
                include = "__all__"
                exclude = {"author_id"}
                model_fk_use_pks = True

        assert "author_id" not in ArticleSchema.model_fields
        assert "author" not in ArticleSchema.model_fields

    def test_exclude_fk_by_original_name(self):
        """Excluding by original name should also work."""

        class ArticleSchema(ModelSchema):
            class Config:
                model = Article
                include = "__all__"
                exclude = {"author"}
                model_fk_use_pks = True

        assert "author_id" not in ArticleSchema.model_fields
        assert "author" not in ArticleSchema.model_fields

    def test_validation_roundtrip(self):
        """Schema can be instantiated with _id values."""

        class ArticleSchema(ModelSchema):
            class Config:
                model = Article
                include = ["id", "title", "author_id"]
                model_fk_use_pks = True

        obj = ArticleSchema(id=1, title="Test", author_id=42)
        assert obj.author_id == 42
        data = obj.model_dump()
        assert data["author_id"] == 42

    def test_model_config_stores_flag(self):
        class ArticleSchema(ModelSchema):
            class Config:
                model = Article
                include = "__all__"
                model_fk_use_pks = True

        assert ArticleSchema._model_config["model_fk_use_pks"] is True

    def test_optional_fields_with_id_name(self):
        """optional config should accept both original and _id names."""

        class ArticleSchema(ModelSchema):
            class Config:
                model = Article
                include = "__all__"
                model_fk_use_pks = True
                optional = {"author_id"}

        import typing

        field_type = ArticleSchema.__annotations__["author_id"]
        args = typing.get_args(field_type)
        assert int in args
        assert type(None) in args
