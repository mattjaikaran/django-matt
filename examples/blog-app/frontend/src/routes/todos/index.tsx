import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useTodos } from '@/hooks/use-todo';
import { useAuth } from '@/lib/store';
import type { Todo, TodoPriority } from '@/types';
import { createFileRoute, Link, Navigate } from '@tanstack/react-router';
import { CheckCircle2, Circle, Plus, Search, Trash2 } from 'lucide-react';
import { useState } from 'react';

export const Route = createFileRoute('/todos/')({
  component: TodosPage,
});

function TodosPage() {
  const { isAuthenticated } = useAuth();
  const { data: todos = [], isLoading } = useTodos();
  const [searchTerm, setSearchTerm] = useState('');
  const [priorityFilter, setPriorityFilter] = useState<TodoPriority | 'all'>(
    'all'
  );
  const [statusFilter, setStatusFilter] = useState<
    'all' | 'completed' | 'pending'
  >('all');

  // Redirect if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/auth/login" />;
  }

  // Filter todos based on search and filters
  const filteredTodos = todos.filter((todo: Todo) => {
    const matchesSearch =
      todo.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      todo.description?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesPriority =
      priorityFilter === 'all' || todo.priority === priorityFilter;
    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'completed' && todo.completed) ||
      (statusFilter === 'pending' && !todo.completed);

    return matchesSearch && matchesPriority && matchesStatus;
  });

  const getPriorityColor = (priority: TodoPriority) => {
    switch (priority) {
      case 'high':
        return 'text-red-600 bg-red-50 border-red-200';
      case 'medium':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'low':
        return 'text-green-600 bg-green-50 border-green-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  return (
    <div className="page-container">
      <div className="space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Todos</h1>
            <p className="text-muted-foreground">
              Manage your tasks and stay organized
            </p>
          </div>
          <Link to="/todos/create">
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Add Todo
            </Button>
          </Link>
        </div>

        {/* Filters */}
        <div className="card-container p-4">
          <div className="flex flex-col gap-4 sm:flex-row">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 transform text-muted-foreground" />
                <Input
                  placeholder="Search todos..."
                  value={searchTerm}
                  onChange={e => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <Select
              value={priorityFilter}
              onValueChange={(value: TodoPriority | 'all') =>
                setPriorityFilter(value)
              }
            >
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Priority" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Priorities</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={statusFilter}
              onValueChange={(value: 'all' | 'completed' | 'pending') =>
                setStatusFilter(value)
              }
            >
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Todo List */}
        <div className="space-y-4">
          {isLoading ? (
            <div className="card-container p-6 text-center">
              <p className="text-muted-foreground">Loading todos...</p>
            </div>
          ) : filteredTodos.length === 0 ? (
            <div className="card-container p-6 text-center">
              <p className="text-muted-foreground">
                {todos.length === 0
                  ? 'No todos yet. Create your first todo to get started!'
                  : 'No todos match your current filters.'}
              </p>
              {todos.length === 0 && (
                <Link to="/todos/create" className="mt-4 inline-block">
                  <Button>
                    <Plus className="mr-2 h-4 w-4" />
                    Create Your First Todo
                  </Button>
                </Link>
              )}
            </div>
          ) : (
            filteredTodos.map((todo: Todo) => (
              <div key={todo.id} className="card-container p-4">
                <div className="flex items-start gap-3">
                  <button className="mt-1">
                    {todo.completed ? (
                      <CheckCircle2 className="h-5 w-5 text-green-600" />
                    ) : (
                      <Circle className="h-5 w-5 text-muted-foreground" />
                    )}
                  </button>

                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center gap-2">
                      <h3
                        className={`font-medium ${todo.completed ? 'text-muted-foreground line-through' : ''}`}
                      >
                        {todo.title}
                      </h3>
                      <span
                        className={`rounded-full border px-2 py-1 text-xs ${getPriorityColor(todo.priority)}`}
                      >
                        {todo.priority}
                      </span>
                    </div>

                    {todo.description && (
                      <p
                        className={`mb-2 text-sm text-muted-foreground ${todo.completed ? 'line-through' : ''}`}
                      >
                        {todo.description}
                      </p>
                    )}

                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      {todo.dueDate && (
                        <span>
                          Due: {new Date(todo.dueDate).toLocaleDateString()}
                        </span>
                      )}
                      {todo.tags.length > 0 && (
                        <div className="flex gap-1">
                          {todo.tags.map(tag => (
                            <span
                              key={tag}
                              className="rounded bg-secondary px-2 py-1"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm">
                      Edit
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
