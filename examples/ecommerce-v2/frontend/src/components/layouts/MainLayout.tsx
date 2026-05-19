import { CartDrawer } from '@/components/cart/CartDrawer';
import { Footer } from '@/components/nav/Footer';
import { Navbar } from '@/components/nav/Navbar';
import { useCart } from '@/hooks/use-cart';
import { useAuth } from '@/lib/store';

export function MainLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  // Pre-fetch cart when authenticated
  useCart();

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="flex-1">{children}</main>
      <Footer />
      {isAuthenticated && <CartDrawer />}
    </div>
  );
}
