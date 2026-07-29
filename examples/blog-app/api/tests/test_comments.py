import pytest

from blog.comments.models import Comment
from blog.posts.models import Post


@pytest.mark.django_db
class TestCommentModel:
    def setup_method(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(
            username="commenter", email="commenter@example.com", password="pass"
        )
        self.post = Post.objects.create(
            title="Post for Comments",
            content="Content",
            author=self.user,
            status="published",
        )

    def test_create_comment(self):
        comment = Comment.objects.create(
            post=self.post,
            author=self.user,
            content="Great post!",
        )
        assert comment.content == "Great post!"
        assert comment.post == self.post

    def test_comment_default_approved(self):
        comment = Comment.objects.create(
            post=self.post,
            content="Auto approved",
        )
        assert comment.is_approved is True

    def test_nested_comment(self):
        parent = Comment.objects.create(
            post=self.post,
            author=self.user,
            content="Parent",
        )
        reply = Comment.objects.create(
            post=self.post,
            author=self.user,
            content="Reply",
            parent=parent,
        )
        assert reply.parent == parent
        assert parent.replies.count() == 1


@pytest.mark.django_db(transaction=True)
class TestCommentAPI:
    def setup_method(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(
            username="apicommenter", email="apicommenter@example.com", password="pass"
        )
        self.post = Post.objects.create(
            title="API Comments Post",
            content="Content",
            author=self.user,
            status="published",
        )

    def test_list_comments_for_post(self, client):
        response = client.get(f"/api/comments/?post={self.post.id}")
        assert response.status_code == 200

    def test_create_comment_unauthenticated(self, client):
        response = client.post(
            "/api/comments/",
            data={"post_id": str(self.post.id), "content": "Test comment", "author_name": "Anon"},
            content_type="application/json",
        )
        assert response.status_code in (200, 201)
