import { Footer } from '@/components/nav/Footer';
import { Navbar } from '@/components/nav/Navbar';
import { Outlet } from '@tanstack/react-router';

interface MainLayoutProps {
  children?: React.ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />

      <main className="flex-1">{children || <Outlet />}</main>

      <Footer />
    </div>
  );
}
