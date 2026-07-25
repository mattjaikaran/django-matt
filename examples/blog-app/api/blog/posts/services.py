"""Business logic for posts app."""

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import F
from django.utils import timezone

from blog.posts.models import Post, PostView


async def get_published_posts(
    *,
    category_slug: str | None = None,
    tag_slug: str | None = None,
    author_username: str | None = None,
    featured: bool | None = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[Post], int]:
    """Return paginated published posts with optional filters."""
    qs = (
        Post.objects.filter(status="published")
        .select_related("author", "author__author_profile", "category")
        .prefetch_related("tags")
        .order_by("-published_at", "-created_at")
    )

    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    if tag_slug:
        qs = qs.filter(tags__slug=tag_slug)
    if author_username:
        qs = qs.filter(author__username=author_username)
    if featured is not None:
        qs = qs.filter(featured=featured)

    total = await qs.acount()
    offset = (page - 1) * page_size
    posts = [p async for p in qs[offset : offset + page_size]]
    return posts, total


async def get_post_by_slug(slug: str) -> Post | None:
    return await (
        Post.objects.filter(slug=slug)
        .select_related("author", "author__author_profile", "category")
        .prefetch_related("tags")
        .afirst()
    )


async def search_posts(query: str, page: int = 1, page_size: int = 10) -> tuple[list[Post], int]:
    """Full-text search across title, content, and excerpt."""
    search_query = SearchQuery(query)
    search_vector = SearchVector("title", weight="A") + SearchVector("excerpt", weight="B") + SearchVector("content", weight="C")

    qs = (
        Post.objects.filter(status="published")
        .annotate(rank=SearchRank(search_vector, search_query))
        .filter(rank__gt=0.01)
        .select_related("author", "author__author_profile", "category")
        .prefetch_related("tags")
        .order_by("-rank", "-published_at")
    )

    total = await qs.acount()
    offset = (page - 1) * page_size
    posts = [p async for p in qs[offset : offset + page_size]]
    return posts, total


async def record_view(post: Post, session_key: str, ip_address: str | None) -> None:
    """Record a unique view, increment counter atomically."""
    created = False
    try:
        _, created = await PostView.objects.aget_or_create(
            post=post,
            session_key=session_key,
            defaults={"ip_address": ip_address},
        )
    except Exception:
        pass

    if created:
        await Post.objects.filter(id=post.id).aupdate(view_count=F("view_count") + 1)


async def publish_post(post: Post) -> Post:
    """Set status to published and stamp published_at if not set."""
    if post.published_at is None:
        post.published_at = timezone.now()
    post.status = "published"
    await post.asave(update_fields=["status", "published_at", "updated_at"])
    return post


def get_seo_meta(post: Post) -> dict:
    site_url = getattr(settings, "SITE_URL", "")
    return {
        "title": post.seo_title or post.title,
        "description": post.seo_description or post.excerpt,
        "og_title": post.seo_title or post.title,
        "og_description": post.seo_description or post.excerpt,
        "og_image": post.cover_image_url,
        "canonical_url": f"{site_url}/blog/{post.slug}",
        "published_at": post.published_at,
        "author": post.author.full_name or post.author.username,
    }
