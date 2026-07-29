import { createRootRoute, Link, Outlet } from '@tanstack/react-router';

export const Route = createRootRoute({
  component: () => (
    <div className="min-h-screen bg-slate-50">
      <nav className="bg-white border-b px-4 py-3 flex gap-4">
        <Link to="/" className="font-semibold text-indigo-600">Starter</Link>
        <Link to="/items" className="text-sm text-slate-600 hover:text-slate-900">Items</Link>
        <div className="flex-1" />
        <Link to="/login" className="text-sm text-slate-600 hover:text-slate-900">Login</Link>
      </nav>
      <main className="container mx-auto px-4 py-8">
        <Outlet />
      </main>
    </div>
  ),
});
