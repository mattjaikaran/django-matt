import { useAuth } from '@/lib/store';
import { Link, useNavigate } from '@tanstack/react-router';
import { LayoutDashboard, Package, ShoppingBag, Store } from 'lucide-react';
import { useEffect } from 'react';
import { Button } from '@/components/ui/button';

const navItems = [
  { href: '/dashboard', label: 'Overview', icon: LayoutDashboard },
  { href: '/dashboard/store', label: 'My Store', icon: Store },
  { href: '/dashboard/products', label: 'Products', icon: Package },
  { href: '/dashboard/orders', label: 'Orders', icon: ShoppingBag },
];

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isAuthenticated) navigate({ to: '/auth/login' });
  }, [isAuthenticated, navigate]);

  if (!isAuthenticated) return null;

  return (
    <div className="flex min-h-[calc(100vh-4rem)]">
      <aside className="w-56 border-r bg-muted/30 p-4 hidden md:block">
        <nav className="space-y-1">
          {navItems.map(({ href, label, icon: Icon }) => (
            <Button key={href} variant="ghost" className="w-full justify-start" asChild>
              <Link to={href as never} activeProps={{ className: 'bg-accent' }}>
                <Icon className="mr-2 h-4 w-4" />
                {label}
              </Link>
            </Button>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
