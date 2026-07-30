import { createFileRoute } from '@tanstack/react-router';
import { useAuth } from '@/hooks/useAuth';
import { ProtectedRoute } from '@/components/ProtectedRoute';

export const Route = createFileRoute('/dashboard')({
  component: () => (
    <ProtectedRoute>
      <DashboardPage />
    </ProtectedRoute>
  ),
});

function DashboardPage() {
  const { user, logout } = useAuth();

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="p-6 border rounded bg-white">
          <h3 className="font-semibold text-lg mb-2">Profile</h3>
          <dl className="space-y-2 text-sm">
            <div>
              <dt className="text-slate-500">Email</dt>
              <dd className="font-medium">{user?.email}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Username</dt>
              <dd className="font-medium">{user?.username}</dd>
            </div>
            <div>
              <dt className="text-slate-500">User ID</dt>
              <dd className="font-medium font-mono text-xs">{user?.id}</dd>
            </div>
          </dl>
        </div>

        <div className="p-6 border rounded bg-white">
          <h3 className="font-semibold text-lg mb-2">Quick Links</h3>
          <div className="space-y-2">
            <a
              href="/items"
              className="block px-3 py-2 bg-indigo-50 text-indigo-700 rounded hover:bg-indigo-100"
            >
              Manage Items &rarr;
            </a>
            <a
              href="/api/docs"
              target="_blank"
              className="block px-3 py-2 bg-slate-50 text-slate-700 rounded hover:bg-slate-100"
              rel="noreferrer"
            >
              API Documentation &#8599;
            </a>
          </div>
        </div>
      </div>

      <div className="mt-8 text-center">
        <button
          onClick={logout}
          className="px-6 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          Logout
        </button>
      </div>
    </div>
  );
}
