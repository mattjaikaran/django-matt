import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { LoginForm } from '@/forms/auth/LoginForm';
import { useAuth } from '@/lib/store';
import { createFileRoute, Navigate } from '@tanstack/react-router';

export const Route = createFileRoute('/auth/login')({
  component: LoginPage,
});

function LoginPage() {
  const { isAuthenticated } = useAuth();

  // Redirect if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/todos" />;
  }

  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md">
        <Card>
          <CardHeader className="space-y-1">
            {/* Header content is handled by LoginForm */}
          </CardHeader>
          <CardContent>
            <LoginForm
              onSuccess={() => {
                // Navigation is handled by the auth store
              }}
              onSwitchToRegister={() => {
                // Navigate to register page
                window.location.href = '/auth/register';
              }}
              onSwitchToMagicLink={() => {
                // Navigate to magic link page
                window.location.href = '/auth/magic-link';
              }}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
