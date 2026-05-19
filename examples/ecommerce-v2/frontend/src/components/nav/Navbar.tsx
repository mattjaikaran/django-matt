import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { useLogout } from '@/hooks/use-auth';
import { useAuth, useCartStore } from '@/lib/store';
import { Link } from '@tanstack/react-router';
import { LayoutDashboard, LogOut, Menu, ShoppingCart, Store, User, X } from 'lucide-react';
import { useState } from 'react';

export function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, isAuthenticated } = useAuth();
  const { cart, setCartOpen } = useCartStore();
  const logoutMutation = useLogout();

  const cartCount = cart?.itemCount ?? 0;

  return (
    <nav className="border-b bg-background sticky top-0 z-30">
      <div className="container mx-auto px-4">
        <div className="flex h-16 items-center justify-between">
          <Link to="/" className="text-xl font-bold text-primary">ShopMatt</Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-6">
            <Link to="/products" className="text-sm font-medium hover:text-primary transition-colors">Products</Link>
            <Link to="/search" className="text-sm font-medium hover:text-primary transition-colors">Search</Link>
            {isAuthenticated && (
              <Link to="/dashboard" className="text-sm font-medium hover:text-primary transition-colors">Dashboard</Link>
            )}
          </div>

          {/* Desktop actions */}
          <div className="hidden md:flex items-center gap-3">
            {isAuthenticated && (
              <Button variant="ghost" size="icon" className="relative" onClick={() => setCartOpen(true)}>
                <ShoppingCart className="h-5 w-5" />
                {cartCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-primary text-primary-foreground text-xs rounded-full w-5 h-5 flex items-center justify-center">
                    {cartCount > 9 ? '9+' : cartCount}
                  </span>
                )}
              </Button>
            )}

            {isAuthenticated ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon">
                    <User className="h-5 w-5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuLabel>
                    <p className="font-medium">{user?.firstName} {user?.lastName}</p>
                    <p className="text-xs text-muted-foreground">{user?.email}</p>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild>
                    <Link to="/profile"><User className="mr-2 h-4 w-4" />Profile</Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to="/orders"><Store className="mr-2 h-4 w-4" />Orders</Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to="/dashboard"><LayoutDashboard className="mr-2 h-4 w-4" />Dashboard</Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => logoutMutation.mutate()}>
                    <LogOut className="mr-2 h-4 w-4" />Log out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <div className="flex gap-2">
                <Button variant="ghost" asChild><Link to="/auth/login">Sign in</Link></Button>
                <Button asChild><Link to="/auth/register">Sign up</Link></Button>
              </div>
            )}
          </div>

          {/* Mobile toggle */}
          <div className="flex md:hidden items-center gap-2">
            {isAuthenticated && (
              <Button variant="ghost" size="icon" className="relative" onClick={() => setCartOpen(true)}>
                <ShoppingCart className="h-5 w-5" />
                {cartCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-primary text-primary-foreground text-xs rounded-full w-5 h-5 flex items-center justify-center">
                    {cartCount > 9 ? '9+' : cartCount}
                  </span>
                )}
              </Button>
            )}
            <Button variant="ghost" size="icon" onClick={() => setMobileOpen(!mobileOpen)}>
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="md:hidden border-t py-4 space-y-2">
            <Link to="/products" className="block px-2 py-2 text-sm hover:text-primary" onClick={() => setMobileOpen(false)}>Products</Link>
            <Link to="/search" className="block px-2 py-2 text-sm hover:text-primary" onClick={() => setMobileOpen(false)}>Search</Link>
            {isAuthenticated ? (
              <>
                <Link to="/orders" className="block px-2 py-2 text-sm hover:text-primary" onClick={() => setMobileOpen(false)}>Orders</Link>
                <Link to="/dashboard" className="block px-2 py-2 text-sm hover:text-primary" onClick={() => setMobileOpen(false)}>Dashboard</Link>
                <button className="block w-full text-left px-2 py-2 text-sm hover:text-primary" onClick={() => { logoutMutation.mutate(); setMobileOpen(false); }}>Log out</button>
              </>
            ) : (
              <>
                <Link to="/auth/login" className="block px-2 py-2 text-sm hover:text-primary" onClick={() => setMobileOpen(false)}>Sign in</Link>
                <Link to="/auth/register" className="block px-2 py-2 text-sm hover:text-primary" onClick={() => setMobileOpen(false)}>Sign up</Link>
              </>
            )}
          </div>
        )}
      </div>
    </nav>
  );
}
