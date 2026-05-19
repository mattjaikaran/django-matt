/**
 * Profile Page
 * User profile view and quick stats
 */

import { DashboardLayout } from '@/components/layouts/DashboardLayout';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { useTodoStats } from '@/hooks';
import { useAuth } from '@/lib/store';
import { createFileRoute, Link } from '@tanstack/react-router';
import { Calendar, Edit, Mail, MapPin, Settings } from 'lucide-react';

export const Route = createFileRoute('/profile' as any)({
  component: ProfilePage,
});

function ProfilePage() {
  const { user } = useAuth();
  const { data: stats } = useTodoStats();

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Profile header */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-col items-start gap-6 sm:flex-row sm:items-center">
              {/* Avatar */}
              <div className="flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/50 text-3xl font-bold text-primary-foreground">
                {user?.firstName?.[0] || user?.email?.[0]?.toUpperCase() || 'U'}
              </div>

              {/* Info */}
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

              {/* Actions */}
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

        {/* Stats */}
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Total Tasks</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{stats?.total || 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Completed</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-emerald-500">
                {stats?.completed || 0}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Pending</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-amber-500">
                {stats?.pending || 0}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Completion Rate</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {stats?.total
                  ? Math.round((stats.completed / stats.total) * 100)
                  : 0}
                %
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Activity section */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>Your latest actions and updates</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[
                {
                  action: 'Completed task',
                  item: 'Review documentation',
                  time: '2 hours ago',
                },
                {
                  action: 'Created task',
                  item: 'Update dependencies',
                  time: '5 hours ago',
                },
                {
                  action: 'Updated profile',
                  item: 'Changed email',
                  time: '1 day ago',
                },
                {
                  action: 'Completed task',
                  item: 'Fix login bug',
                  time: '2 days ago',
                },
              ].map((activity, i) => (
                <div
                  key={i}
                  className="flex items-center gap-4 rounded-lg p-3 transition-colors hover:bg-muted/50"
                >
                  <div className="h-2 w-2 rounded-full bg-primary" />
                  <div className="flex-1">
                    <p className="text-sm">
                      <span className="font-medium">{activity.action}</span>
                      {' · '}
                      <span className="text-muted-foreground">
                        {activity.item}
                      </span>
                    </p>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {activity.time}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
