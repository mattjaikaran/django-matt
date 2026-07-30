import { createRootRoute, Link, Outlet } from '@tanstack/react-router';
import { ShoppingCart, Package, ListOrdered, LogIn, LogOut } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';

export const Route = createRootRoute({
  component: RootLayout,
});

function RootLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <header className="bg-white border-b shadow-sm sticky top-0 z-10">
        <div className="container mx-auto px-4 py-3 flex items-center gap-6">
          <Link to="/" className="text-xl font-bold text-indigo-600 flex items-center gap-2">
            <ShoppingCart className="w-6 h-6" />
            Shop
          </Link>

          <nav className="flex gap-4 text-sm">
            <Link to="/products" className="text-slate-600 hover:text-slate-900 flex items-center gap-1">
              <Package className="w-4 h-4" />
              Products
            </Link>
            <Link to="/cart" className="text-slate-600 hover:text-slate-900 flex items-center gap-1">
              <ShoppingCart className="w-4 h-4" />
              Cart
            </Link>
            <Link to="/orders" className="text-slate-600 hover:text-slate-900 flex items-center gap-1">
              <ListOrdered className="w-4 h-4" />
              Orders
            </Link>
          </nav>

          <div className="flex-1" />

          {user ? (
            <button
              onClick={logout}
              className="text-sm text-slate-600 hover:text-slate-900 flex items-center gap-1"
            >
              <LogOut className="w-4 h-4" />
              Logout
            </button>
          ) : (
            <Link to="/login" className="text-sm text-slate-600 hover:text-slate-900 flex items-center gap-1">
              <LogIn className="w-4 h-4" />
              Login
            </Link>
          )}
        </div>
      </header>

      <main className="flex-1 container mx-auto px-4 py-8">
        <Outlet />
      </main>

      <footer className="bg-white border-t py-6 mt-auto">
        <div className="container mx-auto px-4 text-center text-sm text-slate-500">
          &copy; {new Date().getFullYear()} Shop. Built with React + django-matt.
        </div>
      </footer>
    </div>
  );
}
