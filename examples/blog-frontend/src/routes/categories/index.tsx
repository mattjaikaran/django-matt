import { Skeleton } from '@/components/ui/skeleton';
import { useCategories } from '@/hooks/use-blog';
import { createFileRoute, Link } from '@tanstack/react-router';
import { Folder } from 'lucide-react';

export const Route = createFileRoute('/categories/' as any)({
  component: CategoriesIndexPage,
});

function CategoriesIndexPage() {
  const { data: categories = [], isLoading } = useCategories();

  return (
    <div className="page-container space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Categories</h1>
        <p className="text-muted-foreground mt-1">Browse posts by category.</p>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {categories.map(cat => (
            <Link
              key={cat.id}
              to={`/categories/${cat.slug}` as any}
              className="flex items-start gap-3 rounded-lg border p-4 hover:bg-muted/50 transition-colors"
            >
              <Folder className="h-5 w-5 text-primary mt-0.5 flex-shrink-0" />
              <div>
                <p className="font-semibold">{cat.name}</p>
                {cat.description && (
                  <p className="text-sm text-muted-foreground line-clamp-2 mt-1">
                    {cat.description}
                  </p>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
