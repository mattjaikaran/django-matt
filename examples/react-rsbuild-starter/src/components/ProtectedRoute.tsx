import { type ReactNode } from 'react';
import { redirect } from '@tanstack/react-router';
import { useAuth } from '@/hooks/useAuth';

interface ProtectedRouteProps {
  children: ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { user } = useAuth();
  const hasHydrated = useAuth.persist.hasHydrated();

  if (!hasHydrated) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
      </div>
    );
  }

  if (!user) {
    throw redirect({ to: '/login' });
  }

  return <>{children}</>;
}
