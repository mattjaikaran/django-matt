import { TagBadge } from '@/components/blog/TagBadge';
import { Skeleton } from '@/components/ui/skeleton';
import { useTags } from '@/hooks/use-blog';
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/tags/')({
  component: TagsIndexPage,
});

function TagsIndexPage() {
  const { data: tags = [], isLoading } = useTags();

  return (
    <div className="page-container space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Tags</h1>
        <p className="text-muted-foreground mt-1">
          Browse posts by topic.
        </p>
      </div>

      {isLoading ? (
        <div className="flex flex-wrap gap-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <Skeleton key={i} className="h-7 w-20 rounded-full" />
          ))}
        </div>
      ) : (
        <div className="flex flex-wrap gap-3">
          {tags.map(tag => (
            <TagBadge key={tag.id} tag={tag} variant="outline" />
          ))}
        </div>
      )}
    </div>
  );
}
