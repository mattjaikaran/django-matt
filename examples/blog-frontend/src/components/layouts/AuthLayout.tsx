import { Footer } from '@/components/nav/Footer';
import { Navbar } from '@/components/nav/Navbar';
import { useAuth } from '@/lib/store';
import { Outlet } from '@tanstack/react-router';
// import { useNavigate } from '@tanstack/react-router';
// import { useEffect } from 'react';

interface AuthLayoutProps {
  children?: React.ReactNode;
  requireAuth?: boolean;
}

export function AuthLayout({ children, requireAuth = true }: AuthLayoutProps) {
  const { isAuthenticated, isLoading } = useAuth();
  // const navigate = useNavigate();
  // TODO: Use navigate for redirects after authentication

  // useEffect(() => {
  //   if (!isLoading) {
  //     if (requireAuth && !isAuthenticated) {
  //       // Redirect to login if authentication is required but user is not authenticated
  //       navigate({ to: '/auth/login' });
  //     } else if (!requireAuth && isAuthenticated) {
  //       // Redirect to todos if user is already authenticated and trying to access auth pages
  //       navigate({ to: '/todos' });
  //     }
  //   }
  // }, [isAuthenticated, isLoading, requireAuth, navigate]);

  // Show loading state while checking authentication
  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col">
        <Navbar />
        <main className="flex flex-1 items-center justify-center">
          <div className="text-center">
            <div className="loading-spinner mx-auto mb-4" />
            <p className="text-muted-foreground">Loading...</p>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  // Don't render content if auth requirements aren't met
  if (requireAuth && !isAuthenticated) {
    return null;
  }

  if (!requireAuth && isAuthenticated) {
    return null;
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />

      <main className="flex-1">{children || <Outlet />}</main>

      <Footer />
    </div>
  );
}
