import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useDeletePost, usePosts } from '@/hooks/use-blog';
import { useAuth } from '@/lib/store';
import { formatDate } from '@/lib/utils';
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { Edit, Plus, Trash2 } from 'lucide-react';

export const Route = createFileRoute('/dashboard/')({
  component: DashboardPage,
});

function DashboardPage() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const { data, isLoading } = usePosts({
    page_size: 50,
    status: 'all',
  });
  const deletePost = useDeletePost();

  if (!isAuthenticated) {
    navigate({ to: '/auth/login' } as any);
    return null;
  }

  const handleDelete = (slug: string) => {
    if (confirm('Delete this post permanently?')) {
      deletePost.mutate(slug);
    }
  };

  return (
    <div className="page-container space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground mt-1">Manage your posts.</p>
        </div>
        <Button asChild>
          <Link to="/dashboard/new" as any>
            <Plus className="h-4 w-4 mr-2" />
            New post
          </Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Your Posts</CardTitle>
          <CardDescription>
            {data ? `${data.total} post${data.total !== 1 ? 's' : ''}` : ''}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : !data?.items.length ? (
            <p className="text-muted-foreground py-8 text-center">
              No posts yet.{' '}
              <Link
                to="/dashboard/new"
                className="text-primary hover:underline"
              >
                Create your first post
              </Link>
              .
            </p>
          ) : (
            <div className="divide-y">
              {data.items.map(post => (
                <div
                  key={post.id}
                  className="flex items-center justify-between py-3 gap-4"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Link
                        to={`/posts/${post.slug}` as any}
                        className="font-medium hover:text-primary truncate"
                      >
                        {post.title}
                      </Link>
                      <Badge
                        variant={
                          post.status === 'published' ? 'default' : 'secondary'
                        }
                      >
                        {post.status}
                      </Badge>
                      {post.featured && (
                        <Badge variant="outline">Featured</Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {post.publishedAt
                        ? formatDate(post.publishedAt)
                        : 'Not published'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <Button variant="ghost" size="icon" asChild>
                      <Link to={`/dashboard/edit/${post.slug}` as any}>
                        <Edit className="h-4 w-4" />
                      </Link>
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(post.slug)}
                      disabled={deletePost.isPending}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
