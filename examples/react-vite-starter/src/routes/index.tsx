import { createFileRoute, Link } from '@tanstack/react-router';
import { useAuth } from '@/hooks/useAuth';

export const Route = createFileRoute('/')({
  component: HomePage,
});

function HomePage() {
  const { user } = useAuth();

  return (
    <div className="text-center py-16">
      <h1 className="text-4xl font-bold text-slate-900 mb-4">
        React + Vite Starter
      </h1>
      <p className="text-lg text-slate-500 mb-8 max-w-lg mx-auto">
        A production-ready React frontend for django-matt APIs. TanStack Router,
        React Query, Zustand auth, and Tailwind CSS — all pre-configured.
      </p>
      <div className="flex gap-4 justify-center">
        {user ? (
          <Link
            to="/dashboard"
            className="px-5 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            Go to Dashboard &rarr;
          </Link>
        ) : (
          <>
            <Link
              to="/items"
              className="px-5 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              Explore Items &rarr;
            </Link>
            <Link
              to="/login"
              className="px-5 py-2.5 border border-slate-300 rounded-lg hover:bg-slate-100"
            >
              Login
            </Link>
          </>
        )}
        <a
          href="/api/docs"
          target="_blank"
          className="px-5 py-2.5 border border-slate-300 rounded-lg hover:bg-slate-100"
          rel="noreferrer"
        >
          API Docs &#8599;
        </a>
      </div>

      <div className="mt-16 grid gap-6 md:grid-cols-3 max-w-3xl mx-auto text-left">
        <div className="p-4 border rounded bg-white">
          <h3 className="font-semibold mb-1">Type-Safe Routing</h3>
          <p className="text-sm text-slate-500">TanStack Router with file-based routes, auto-complete, and code splitting.</p>
        </div>
        <div className="p-4 border rounded bg-white">
          <h3 className="font-semibold mb-1">JWT Auth Ready</h3>
          <p className="text-sm text-slate-500">Zustand store with login, register, logout, and automatic token refresh.</p>
        </div>
        <div className="p-4 border rounded bg-white">
          <h3 className="font-semibold mb-1">API Integration</h3>
          <p className="text-sm text-slate-500">Axios client with interceptors, React Query hooks, and sync_types support.</p>
        </div>
      </div>
    </div>
  );
}
