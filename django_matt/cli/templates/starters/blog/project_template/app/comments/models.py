from django.db import models


class Comment(models.Model):
    post = models.ForeignKey(
        "posts.Post", on_delete=models.CASCADE, related_name="comments"
    )
    author_name = models.CharField(max_length=100)
    author_email = models.EmailField()
    body = models.TextField()
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "comments"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment by {self.author_name} on {self.post_id}"
