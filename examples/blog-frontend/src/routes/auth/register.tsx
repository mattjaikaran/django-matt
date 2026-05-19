import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { RegisterForm } from '@/forms/auth/RegisterForm';
import { useAuth } from '@/lib/store';
import { createFileRoute, Navigate } from '@tanstack/react-router';

export const Route = createFileRoute('/auth/register')({
  component: RegisterPage,
});

function RegisterPage() {
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
            {/* Header content is handled by RegisterForm */}
          </CardHeader>
          <CardContent>
            <RegisterForm
              onSuccess={() => {
                // Navigation is handled by the auth store
              }}
              onSwitchToLogin={() => {
                // Navigate to login page
                window.location.href = '/auth/login';
              }}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
