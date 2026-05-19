import { AuthorCard } from '@/components/blog/AuthorCard';
import { CommentForm } from '@/components/blog/CommentForm';
import { CommentThread } from '@/components/blog/CommentThread';
import { TagBadge } from '@/components/blog/TagBadge';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useComments, usePost } from '@/hooks/use-blog';
import { formatDate } from '@/lib/utils';
import { createFileRoute, Link } from '@tanstack/react-router';
import { ArrowLeft, Clock, Eye, Folder } from 'lucide-react';

export const Route = createFileRoute('/posts/$slug')({
  component: PostDetailPage,
});

function PostDetailPage() {
  const { slug } = Route.useParams() as { slug: string };
  const { data: post, isLoading } = usePost(slug);
  const { data: comments = [] } = useComments(post?.id ?? '');

  if (isLoading) {
    return (
      <div className="page-container space-y-6">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-64 w-full rounded-lg" />
        <div className="space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-4 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (!post) {
    return (
      <div className="page-container py-16 text-center">
        <h1 className="text-2xl font-bold">Post not found</h1>
        <Link to="/" className="mt-4 inline-block text-primary hover:underline">
          Back to home
        </Link>
      </div>
    );
  }

  return (
    <div className="page-container space-y-8">
      {/* Back link */}
      <Link
        to="/"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        All posts
      </Link>

      {/* Header */}
      <div className="space-y-4">
        {post.category && (
          <Link to={`/categories/${post.category.slug}` as any}>
            <span className="text-sm font-semibold text-primary uppercase tracking-wide hover:underline flex items-center gap-1">
              <Folder className="h-3 w-3" />
              {post.category.name}
            </span>
          </Link>
        )}

        <h1 className="text-4xl font-bold leading-tight">{post.title}</h1>

        <p className="text-lg text-muted-foreground">{post.excerpt}</p>

        <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
          <AuthorCard author={post.author} size="sm" />
          {post.publishedAt && (
            <span>{formatDate(post.publishedAt)}</span>
          )}
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {post.readingTimeMinutes} min read
          </span>
          <span className="flex items-center gap-1">
            <Eye className="h-3 w-3" />
            {post.viewCount} views
          </span>
          {post.featured && (
            <Badge variant="default">Featured</Badge>
          )}
        </div>

        {post.tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {post.tags.map(tag => (
              <TagBadge key={tag.id} tag={tag} />
            ))}
          </div>
        )}
      </div>

      {/* Cover image */}
      {post.coverImageUrl && (
        <div className="aspect-video overflow-hidden rounded-lg">
          <img
            src={post.coverImageUrl}
            alt={post.title}
            className="h-full w-full object-cover"
          />
        </div>
      )}

      {/* Content */}
      <div className="prose prose-neutral dark:prose-invert max-w-none">
        <div className="whitespace-pre-wrap text-base leading-relaxed">
          {post.content}
        </div>
      </div>

      {/* Author card */}
      <div className="border rounded-lg p-6">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
          Written by
        </h3>
        <AuthorCard author={post.author} />
      </div>

      {/* Comments */}
      <div className="space-y-6">
        <h2 className="text-2xl font-bold">
          Comments ({comments.length})
        </h2>
        <CommentThread comments={comments} postId={post.id} />
        <div className="border-t pt-6">
          <h3 className="text-lg font-semibold mb-4">Leave a comment</h3>
          <CommentForm postId={post.id} />
        </div>
      </div>
    </div>
  );
}
