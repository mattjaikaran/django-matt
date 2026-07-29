import pytest

from blog.posts.models import Category, Post, Tag


@pytest.mark.django_db
class TestTagModel:
    def test_create_tag(self):
        tag = Tag.objects.create(name="Python")
        assert tag.slug == "python"
        assert str(tag) == "Python"

    def test_tag_slug_auto_generated(self):
        tag = Tag.objects.create(name="Django REST Framework")
        assert tag.slug == "django-rest-framework"

    def test_tag_unique_name(self):
        Tag.objects.create(name="Unique")
        with pytest.raises(Exception):
            Tag.objects.create(name="Unique")


@pytest.mark.django_db
class TestCategoryModel:
    def test_create_category(self):
        cat = Category.objects.create(name="Technology")
        assert cat.slug == "technology"
        assert str(cat) == "Technology"

    def test_category_parent(self):
        parent = Category.objects.create(name="Tech")
        child = Category.objects.create(name="Python", parent=parent)
        assert child.parent == parent
        assert parent.children.count() == 1


@pytest.mark.django_db
class TestPostModel:
    def setup_method(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(
            username="author", email="author@example.com", password="pass"
        )

    def test_create_draft_post(self):
        post = Post.objects.create(
            title="My First Post",
            content="Hello world",
            author=self.user,
        )
        assert post.status == "draft"
        assert post.slug == "my-first-post"

    def test_post_slug_auto_generated(self):
        post = Post.objects.create(
            title="Hello World Post",
            content="Content here",
            author=self.user,
        )
        assert post.slug == "hello-world-post"

    def test_published_post(self):
        from django.utils import timezone

        post = Post.objects.create(
            title="Published",
            content="Content",
            author=self.user,
            status="published",
            published_at=timezone.now(),
        )
        assert post.status == "published"
        assert post.published_at is not None

    def test_post_with_tags(self):
        tag = Tag.objects.create(name="Django")
        post = Post.objects.create(
            title="Django Post",
            content="Content",
            author=self.user,
        )
        post.tags.add(tag)
        assert post.tags.count() == 1
        assert post.tags.first().name == "Django"


@pytest.mark.django_db
class TestPostAPI:
    def test_list_posts_public(self, client):
        response = client.get("/api/posts/")
        assert response.status_code == 200

    def test_get_nonexistent_post(self, client):
        response = client.get("/api/posts/does-not-exist/")
        assert response.status_code == 404

    def test_list_tags(self, client):
        Tag.objects.create(name="API")
        Tag.objects.create(name="Testing")
        response = client.get("/api/tags/")
        assert response.status_code == 200

    def test_list_categories(self, client):
        Category.objects.create(name="Dev")
        response = client.get("/api/categories/")
        assert response.status_code == 200

    def test_create_post_requires_auth(self, client):
        response = client.post(
            "/api/posts/",
            data={"title": "Test", "content": "Content"},
            content_type="application/json",
        )
        assert response.status_code in (401, 403)

    def test_search_posts(self, client):
        import django

        if django.db.connections["default"].vendor == "sqlite":
            pytest.skip("Full-text search requires PostgreSQL")
        response = client.get("/api/posts/search?q=django")
