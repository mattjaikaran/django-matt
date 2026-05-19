import { api } from '@/lib/api';
import type {
  CreateTodoRequest,
  Todo,
  TodoFilters,
  TodoState,
  UpdateTodoRequest,
} from '@/types';
import { StateCreator } from 'zustand';

export interface TodoSlice extends TodoState {
  // Actions
  fetchTodos: () => Promise<void>;
  createTodo: (todo: CreateTodoRequest) => Promise<void>;
  updateTodo: (id: string, updates: UpdateTodoRequest) => Promise<void>;
  deleteTodo: (id: string) => Promise<void>;
  toggleTodo: (id: string) => Promise<void>;
  setFilters: (filters: Partial<TodoFilters>) => void;
  clearFilters: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearError: () => void;
}

const initialFilters: TodoFilters = {
  search: '',
  priority: 'all',
  completed: 'all',
  tags: [],
};

const initialState: TodoState = {
  todos: [],
  isLoading: false,
  error: null,
  filters: initialFilters,
};

export const createTodoSlice: StateCreator<TodoSlice> = (set, get) => ({
  ...initialState,

  fetchTodos: async () => {
    set({ isLoading: true, error: null });

    try {
      const response = await api.get<Todo[]>('/todos');
      set({
        todos: response.data,
        isLoading: false,
        error: null,
      });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to fetch todos',
      });
    }
  },

  createTodo: async (todoData: CreateTodoRequest) => {
    set({ isLoading: true, error: null });

    try {
      const response = await api.post<Todo>('/todos', todoData);
      const { todos } = get();
      set({
        todos: [response.data, ...todos],
        isLoading: false,
        error: null,
      });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to create todo',
      });
    }
  },

  updateTodo: async (id: string, updates: UpdateTodoRequest) => {
    set({ isLoading: true, error: null });

    try {
      const response = await api.patch<Todo>(`/todos/${id}`, updates);
      const { todos } = get();
      set({
        todos: todos.map(todo => (todo.id === id ? response.data : todo)),
        isLoading: false,
        error: null,
      });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to update todo',
      });
    }
  },

  deleteTodo: async (id: string) => {
    set({ isLoading: true, error: null });

    try {
      await api.delete(`/todos/${id}`);
      const { todos } = get();
      set({
        todos: todos.filter(todo => todo.id !== id),
        isLoading: false,
        error: null,
      });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to delete todo',
      });
    }
  },

  toggleTodo: async (id: string) => {
    const { todos } = get();
    const todo = todos.find(t => t.id === id);

    if (todo) {
      try {
        const response = await api.patch<Todo>(`/todos/${id}`, {
          completed: !todo.completed,
        });
        set({
          todos: todos.map(t => (t.id === id ? response.data : t)),
        });
      } catch (error) {
        set({
          error: error instanceof Error ? error.message : 'Failed to toggle todo',
        });
      }
    }
  },

  setFilters: (newFilters: Partial<TodoFilters>) => {
    const { filters } = get();
    set({
      filters: { ...filters, ...newFilters },
    });
  },

  clearFilters: () => {
    set({ filters: initialFilters });
  },

  setLoading: (isLoading: boolean) => {
    set({ isLoading });
  },

  setError: (error: string | null) => {
    set({ error });
  },

  clearError: () => {
    set({ error: null });
  },
});
