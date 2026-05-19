import { PostList } from '@/components/blog/PostList';
import { SearchBar } from '@/components/blog/SearchBar';
import { Skeleton } from '@/components/ui/skeleton';
import { useSearchPosts } from '@/hooks/use-blog';
import { createFileRoute } from '@tanstack/react-router';
import { z } from 'zod';

const searchSchema = z.object({
  q: z.string().default(''),
});

export const Route = createFileRoute('/search' as any)({
  validateSearch: searchSchema,
  component: SearchPage,
});

function SearchPage() {
  const { q } = Route.useSearch() as { q: string };
  const { data: results = [], isLoading } = useSearchPosts(q);

  return (
    <div className="page-container space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Search</h1>
        {q && (
          <p className="text-muted-foreground mt-1">
            Results for &ldquo;{q}&rdquo;
          </p>
        )}
      </div>

      <div className="max-w-xl">
        <SearchBar defaultValue={q} placeholder="Search posts…" />
      </div>

      {q.length < 2 ? (
        <p className="text-muted-foreground">
          Enter at least 2 characters to search.
        </p>
      ) : isLoading ? (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-72 rounded-lg" />
          ))}
        </div>
      ) : (
        <PostList
          posts={results}
          emptyMessage={`No results for "${q}".`}
        />
      )}
    </div>
  );
}
