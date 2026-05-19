import { Link } from '@tanstack/react-router';

export function Footer() {
  return (
    <footer className="border-t bg-background mt-auto">
      <div className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div>
            <h3 className="font-semibold mb-3">ShopMatt</h3>
            <p className="text-sm text-muted-foreground">Multi-vendor marketplace built with django-matt.</p>
          </div>
          <div>
            <h3 className="font-semibold mb-3">Shop</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link to="/products" className="hover:text-foreground">All Products</Link></li>
              <li><Link to="/search" className="hover:text-foreground">Search</Link></li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold mb-3">Account</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link to="/auth/login" className="hover:text-foreground">Sign In</Link></li>
              <li><Link to="/orders" className="hover:text-foreground">Orders</Link></li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold mb-3">Sell</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link to="/dashboard" className="hover:text-foreground">Vendor Dashboard</Link></li>
            </ul>
          </div>
        </div>
        <div className="border-t mt-8 pt-6 text-center text-sm text-muted-foreground">
          <p>Built with django-matt · {new Date().getFullYear()}</p>
        </div>
      </div>
    </footer>
  );
}
