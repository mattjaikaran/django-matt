import { Pagination } from '@/components/blog/Pagination';
import { PostList } from '@/components/blog/PostList';
import { Skeleton } from '@/components/ui/skeleton';
import { usePosts, useTag } from '@/hooks/use-blog';
import { createFileRoute, Link } from '@tanstack/react-router';
import { ArrowLeft } from 'lucide-react';
import { useState } from 'react';

export const Route = createFileRoute('/tags/$slug')({
  component: TagPage,
});

function TagPage() {
  const { slug } = Route.useParams() as { slug: string };
  const { data: tag } = useTag(slug);
  const [page, setPage] = useState(1);
  const { data, isLoading } = usePosts({ tag: slug, page, page_size: 9 });

  return (
    <div className="page-container space-y-8">
      <Link
        to="/"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        All posts
      </Link>

      <div>
        <p className="text-sm text-muted-foreground uppercase tracking-wide">
          Tag
        </p>
        <h1 className="text-3xl font-bold">{tag?.name ?? slug}</h1>
      </div>

      {isLoading ? (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-72 rounded-lg" />
          ))}
        </div>
      ) : (
        <PostList
          posts={data?.items ?? []}
          emptyMessage={`No posts tagged "${tag?.name ?? slug}".`}
        />
      )}

      {data && data.totalPages > 1 && (
        <Pagination
          page={data.page}
          totalPages={data.totalPages}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
