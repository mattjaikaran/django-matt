import { createRootRoute, Link, Outlet } from '@tanstack/react-router';
import { useAuth } from '@/hooks/useAuth';

function NavBar() {
  const { user, logout } = useAuth();

  return (
    <nav className="bg-white border-b px-4 py-3 flex gap-4 items-center">
      <Link to="/" className="font-semibold text-indigo-600">django-matt Starter</Link>
      <Link to="/items" className="text-sm text-slate-600 hover:text-slate-900">Items</Link>
      {user && (
        <Link to="/dashboard" className="text-sm text-slate-600 hover:text-slate-900">Dashboard</Link>
      )}
      <div className="flex-1" />
      {user ? (
        <button onClick={logout} className="text-sm text-slate-600 hover:text-slate-900">
          Logout ({user.email})
        </button>
      ) : (
        <Link to="/login" className="text-sm text-slate-600 hover:text-slate-900">Login</Link>
      )}
    </nav>
  );
}

export const Route = createRootRoute({
  component: () => (
    <div className="min-h-screen bg-slate-50">
      <NavBar />
      <main className="container mx-auto px-4 py-8">
        <Outlet />
      </main>
    </div>
  ),
});
