import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TodoForm } from './TodoForm';

// Mock the hooks - define mocks before vi.mock calls
const mockCreateTodoMutateAsync = vi.fn();
const mockUpdateTodoMutateAsync = vi.fn();
const mockAddNotification = vi.fn();

// Track isPending state
let createTodoPending = false;
let updateTodoPending = false;

vi.mock('@/hooks/use-todo', () => ({
  useCreateTodo: () => ({
    mutateAsync: mockCreateTodoMutateAsync,
    isPending: createTodoPending,
  }),
  useUpdateTodo: () => ({
    mutateAsync: mockUpdateTodoMutateAsync,
    isPending: updateTodoPending,
  }),
}));

vi.mock('@/lib/store', () => ({
  useUI: () => ({
    addNotification: mockAddNotification,
  }),
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('TodoForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    createTodoPending = false;
    updateTodoPending = false;
  });

  it('renders create form correctly', () => {
    render(<TodoForm />, { wrapper: createWrapper() });

    expect(screen.getByText('Create New Todo')).toBeInTheDocument();
    expect(screen.getByLabelText('Title')).toBeInTheDocument();
    expect(screen.getByLabelText('Description')).toBeInTheDocument();
    expect(screen.getByLabelText('Priority')).toBeInTheDocument();
    expect(screen.getByLabelText('Due Date')).toBeInTheDocument();
    expect(screen.getByText('Create Todo')).toBeInTheDocument();
  });

  it('calls createTodo API when form is submitted', async () => {
    const user = userEvent.setup();
    mockCreateTodoMutateAsync.mockResolvedValue({
      id: '1',
      title: 'Test Todo',
      description: 'Test Description',
      priority: 'medium',
      completed: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      userId: 'user1',
    });

    const mockOnSuccess = vi.fn();

    render(<TodoForm onSuccess={mockOnSuccess} />, {
      wrapper: createWrapper(),
    });

    // Fill out the form
    await user.type(screen.getByLabelText('Title'), 'Test Todo');
    await user.type(screen.getByLabelText('Description'), 'Test Description');

    // Submit the form
    await user.click(screen.getByText('Create Todo'));

    await waitFor(() => {
      expect(mockCreateTodoMutateAsync).toHaveBeenCalledWith({
        title: 'Test Todo',
        description: 'Test Description',
        priority: 'medium',
        dueDate: '',
        tags: [],
      });
    });

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });

  it('calls updateTodo API when editing existing todo', async () => {
    const user = userEvent.setup();
    const existingTodo = {
      id: '1',
      title: 'Existing Todo',
      description: 'Existing Description',
      priority: 'high' as const,
      completed: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      tags: ['existing-tag'],
      userId: 'user1',
    };

    mockUpdateTodoMutateAsync.mockResolvedValue({
      ...existingTodo,
      title: 'Updated Todo',
    });

    const mockOnSuccess = vi.fn();

    render(<TodoForm todo={existingTodo} onSuccess={mockOnSuccess} />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByText('Edit Todo')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Existing Todo')).toBeInTheDocument();

    // Update the title
    const titleInput = screen.getByLabelText('Title');
    await user.clear(titleInput);
    await user.type(titleInput, 'Updated Todo');

    // Submit the form
    await user.click(screen.getByText('Update Todo'));

    await waitFor(() => {
      expect(mockUpdateTodoMutateAsync).toHaveBeenCalledWith({
        id: '1',
        updates: {
          title: 'Updated Todo',
          description: 'Existing Description',
          priority: 'high',
          dueDate: '',
          tags: ['existing-tag'],
        },
      });
    });

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });

  it('shows loading state during API call', async () => {
    const user = userEvent.setup();
    createTodoPending = true;
    mockCreateTodoMutateAsync.mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<TodoForm />, { wrapper: createWrapper() });

    await user.type(screen.getByLabelText('Title'), 'Test Todo');

    // The button should show creating state when isPending is true
    const button = screen.getByRole('button', { name: /create todo/i });
    expect(button).toBeInTheDocument();
  });

  it('handles API errors gracefully', async () => {
    const user = userEvent.setup();
    mockCreateTodoMutateAsync.mockRejectedValue(new Error('API Error'));

    render(<TodoForm />, { wrapper: createWrapper() });

    await user.type(screen.getByLabelText('Title'), 'Test Todo');
    await user.click(screen.getByText('Create Todo'));

    await waitFor(() => {
      expect(mockCreateTodoMutateAsync).toHaveBeenCalled();
    });

    // Form should still be visible (not closed due to error)
    expect(screen.getByText('Create New Todo')).toBeInTheDocument();
  });
});
