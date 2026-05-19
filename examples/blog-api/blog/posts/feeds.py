"""RSS feed for published posts."""

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed

from blog.posts.models import Post


class LatestPostsFeed(Feed):
    title = getattr(settings, "BLOG_TITLE", "Blog")
    description = getattr(settings, "BLOG_DESCRIPTION", "")
    link = "/"

    def items(self):
        return Post.objects.filter(status="published").select_related("author").order_by(
            "-published_at"
        )[:20]

    def item_title(self, item: Post) -> str:
        return item.title

    def item_description(self, item: Post) -> str:
        return item.excerpt

    def item_pubdate(self, item: Post):
        return item.published_at

    def item_author_name(self, item: Post) -> str:
        return item.author.full_name or item.author.username

    def item_link(self, item: Post) -> str:
        frontend_url = getattr(settings, "FRONTEND_URL", "")
        return f"{frontend_url}/blog/{item.slug}"


class LatestPostsAtomFeed(LatestPostsFeed):
    feed_type = Atom1Feed
    subtitle = LatestPostsFeed.description
