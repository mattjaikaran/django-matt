import { TodoForm } from '@/forms/todos/TodoForm';
// import { useAuth } from '@/lib/store';
import { createFileRoute, useNavigate } from '@tanstack/react-router';

export const Route = createFileRoute('/todos/create')({
  component: CreateTodoPage,
});

function CreateTodoPage() {
  // const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  // Redirect if not authenticated
  // if (!isAuthenticated) {
  //   return <Navigate to="/auth/login" />;
  // }

  const handleSuccess = () => {
    navigate({ to: '/todos' });
  };

  const handleCancel = () => {
    navigate({ to: '/todos' });
  };

  return (
    <div className="page-container">
      <div className="mx-auto max-w-2xl space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Create Todo</h1>
            <p className="text-muted-foreground">
              Add a new task to your todo list
            </p>
          </div>
        </div>

        <div className="card-container p-6">
          <TodoForm onSuccess={handleSuccess} onCancel={handleCancel} />
        </div>
      </div>
    </div>
  );
}
