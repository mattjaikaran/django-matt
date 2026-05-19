import { Pagination } from '@/components/blog/Pagination';
import { PostFilters } from '@/components/blog/PostFilters';
import { PostList } from '@/components/blog/PostList';
import { SearchBar } from '@/components/blog/SearchBar';
import { Skeleton } from '@/components/ui/skeleton';
import { usePosts } from '@/hooks/use-blog';
import type { PostListParams } from '@/types/blog';
import { createFileRoute } from '@tanstack/react-router';
import { useState } from 'react';

export const Route = createFileRoute('/')({
  component: HomePage,
});

function HomePage() {
  const [params, setParams] = useState<PostListParams>({
    page: 1,
    page_size: 9,
  });

  const { data, isLoading } = usePosts(params);

  return (
    <div className="page-container space-y-8">
      <div className="space-y-2">
        <h1 className="text-4xl font-bold">The Blog</h1>
        <p className="text-muted-foreground">
          Stories, tutorials, and insights.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <PostFilters params={params} onChange={setParams} />
        <div className="w-full sm:w-72">
          <SearchBar />
        </div>
      </div>

      {isLoading ? (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-72 rounded-lg" />
          ))}
        </div>
      ) : (
        <PostList posts={data?.items ?? []} />
      )}

      {data && data.totalPages > 1 && (
        <Pagination
          page={data.page}
          totalPages={data.totalPages}
          onPageChange={page => setParams(p => ({ ...p, page }))}
        />
      )}
    </div>
  );
}
