import { DashboardLayout } from '@/components/layouts/DashboardLayout';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { usePosts } from '@/hooks/use-blog';
import type { Post } from '@/types';
import { useAuth } from '@/lib/store';
import { createFileRoute, Link } from '@tanstack/react-router';
import { Calendar, Edit, Mail, MapPin, Settings } from 'lucide-react';

export const Route = createFileRoute('/profile/')({
  component: ProfilePage,
});

function ProfilePage() {
  const { user } = useAuth();
  const { data: postsData } = usePosts({ author: user?.id?.toString() });
  const posts: Post[] = postsData?.items ?? [];
  const publishedCount = posts.filter((p: Post) => p.status === 'published').length;
  const draftCount = posts.filter((p: Post) => p.status === 'draft').length;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-col items-start gap-6 sm:flex-row sm:items-center">
              <div className="flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/50 text-3xl font-bold text-primary-foreground">
                {user?.firstName?.[0] || user?.email?.[0]?.toUpperCase() || 'U'}
              </div>

              <div className="flex-1">
                <h1 className="text-2xl font-bold">
                  {user?.firstName && user?.lastName
                    ? `${user.firstName} ${user.lastName}`
                    : 'User'}
                </h1>
                <div className="mt-2 flex flex-wrap gap-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Mail className="h-4 w-4" />
                    {user?.email || 'No email'}
                  </span>
                  <span className="flex items-center gap-1">
                    <Calendar className="h-4 w-4" />
                    Joined {new Date().toLocaleDateString()}
                  </span>
                  <span className="flex items-center gap-1">
                    <MapPin className="h-4 w-4" />
                    Location not set
                  </span>
                </div>
              </div>

              <div className="flex gap-2">
                <Button variant="outline" size="sm" asChild>
                  <Link to={'/settings' as any}>
                    <Edit className="mr-2 h-4 w-4" />
                    Edit Profile
                  </Link>
                </Button>
                <Button variant="ghost" size="icon" asChild>
                  <Link to={'/settings' as any}>
                    <Settings className="h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Total Posts</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{posts.length}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Published</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-emerald-500">
                {publishedCount}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Drafts</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-amber-500">
                {draftCount}
              </div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Recent Posts</CardTitle>
            <CardDescription>Your latest articles</CardDescription>
          </CardHeader>
          <CardContent>
            {posts.length === 0 ? (
              <p className="text-sm text-muted-foreground">No posts yet.</p>
            ) : (
              <div className="space-y-3">
                {posts.slice(0, 5).map(post => (
                  <div
                    key={post.id}
                    className="flex items-center gap-4 rounded-lg p-3 transition-colors hover:bg-muted/50"
                  >
                    <div className="h-2 w-2 rounded-full bg-primary" />
                    <div className="flex-1">
                      <p className="text-sm font-medium">{post.title}</p>
                      <p className="text-xs text-muted-foreground capitalize">
                        {post.status}
                      </p>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {new Date(post.createdAt).toLocaleDateString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
