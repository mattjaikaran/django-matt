import type { Post } from '@/types/blog';
import { PostCard } from './PostCard';

interface PostListProps {
  posts: Post[];
  emptyMessage?: string;
}

export function PostList({
  posts,
  emptyMessage = 'No posts found.',
}: PostListProps) {
  if (posts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <p className="text-lg">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {posts.map(post => (
        <PostCard key={post.id} post={post} />
      ))}
    </div>
  );
}
