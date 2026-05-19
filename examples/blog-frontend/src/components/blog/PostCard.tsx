import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from '@/components/ui/card';
import { formatDate } from '@/lib/utils';
import type { Post } from '@/types/blog';
import { Link } from '@tanstack/react-router';
import { Clock, Eye } from 'lucide-react';
import { AuthorCard } from './AuthorCard';
import { TagBadge } from './TagBadge';

interface PostCardProps {
  post: Post;
}

export function PostCard({ post }: PostCardProps) {
  return (
    <Card className="flex flex-col overflow-hidden hover:shadow-md transition-shadow">
      {post.coverImageUrl && (
        <Link to={`/posts/${post.slug}` as any}>
          <div className="aspect-video overflow-hidden">
            <img
              src={post.coverImageUrl}
              alt={post.title}
              className="h-full w-full object-cover transition-transform hover:scale-105"
            />
          </div>
        </Link>
      )}

      <CardHeader className="pb-2">
        {post.category && (
          <Link to={`/categories/${post.category.slug}` as any}>
            <span className="text-xs font-semibold text-primary uppercase tracking-wide hover:underline">
              {post.category.name}
            </span>
          </Link>
        )}
        <Link to={`/posts/${post.slug}` as any}>
          <h2 className="text-xl font-bold leading-snug hover:text-primary transition-colors line-clamp-2">
            {post.title}
          </h2>
        </Link>
      </CardHeader>

      <CardContent className="flex-1 pb-2">
        <p className="text-sm text-muted-foreground line-clamp-3">
          {post.excerpt}
        </p>
      </CardContent>

      <CardFooter className="flex flex-col items-start gap-3 pt-2">
        <div className="flex flex-wrap gap-1">
          {post.tags.slice(0, 3).map(tag => (
            <TagBadge key={tag.id} tag={tag} />
          ))}
        </div>

        <div className="flex items-center justify-between w-full">
          <AuthorCard author={post.author} size="sm" />
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {post.readingTimeMinutes}m
            </span>
            <span className="flex items-center gap-1">
              <Eye className="h-3 w-3" />
              {post.viewCount}
            </span>
          </div>
        </div>

        {post.publishedAt && (
          <p className="text-xs text-muted-foreground">
            {formatDate(post.publishedAt)}
          </p>
        )}
      </CardFooter>
    </Card>
  );
}
