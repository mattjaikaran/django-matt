import type {
  AuthResponse,
  CreateTodoRequest,
  Todo,
  UpdateTodoRequest,
  User,
} from '@/types';

// Mock data
const mockUser: User = {
  id: '1',
  email: 'demo@example.com',
  firstName: 'Demo',
  lastName: 'User',
  isActive: true,
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-01T00:00:00Z',
};

const mockTodos: Todo[] = [
  {
    id: '1',
    title: 'Complete project setup',
    description:
      'Set up the React Vite boilerplate with all necessary configurations',
    completed: false,
    priority: 'high',
    dueDate: '2024-12-31',
    tags: ['development', 'setup'],
    userId: '1',
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: '2',
    title: 'Write documentation',
    description: 'Create comprehensive documentation for the boilerplate',
    completed: false,
    priority: 'medium',
    dueDate: '2024-12-25',
    tags: ['documentation', 'writing'],
    userId: '1',
    createdAt: '2024-01-02T00:00:00Z',
    updatedAt: '2024-01-02T00:00:00Z',
  },
  {
    id: '3',
    title: 'Add unit tests',
    description: 'Implement unit tests for all components and utilities',
    completed: true,
    priority: 'high',
    tags: ['testing', 'quality'],
    userId: '1',
    createdAt: '2024-01-03T00:00:00Z',
    updatedAt: '2024-01-03T00:00:00Z',
  },
  {
    id: '4',
    title: 'Optimize performance',
    description: 'Review and optimize application performance',
    completed: false,
    priority: 'medium',
    tags: ['performance', 'optimization'],
    userId: '1',
    createdAt: '2024-01-04T00:00:00Z',
    updatedAt: '2024-01-04T00:00:00Z',
  },
  {
    id: '5',
    title: 'Deploy to production',
    description: 'Set up CI/CD pipeline and deploy to production environment',
    completed: false,
    priority: 'low',
    dueDate: '2025-01-15',
    tags: ['deployment', 'devops'],
    userId: '1',
    createdAt: '2024-01-05T00:00:00Z',
    updatedAt: '2024-01-05T00:00:00Z',
  },
];

// Utility functions
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

const generateId = () => Math.random().toString(36).substr(2, 9);

// Mock API functions
export const mockApi = {
  // Auth endpoints
  auth: {
    login: async (credentials: {
      email: string;
      password: string;
    }): Promise<AuthResponse> => {
      await delay(800); // Simulate network delay

      if (
        credentials.email === 'demo@example.com' &&
        credentials.password === 'password'
      ) {
        return {
          user: mockUser,
          tokens: {
            accessToken: 'mock-access-token-' + Date.now(),
            refreshToken: 'mock-refresh-token-' + Date.now(),
          },
        };
      }

      throw new Error('Invalid credentials');
    },

    register: async (credentials: {
      email: string;
      password: string;
      firstName: string;
      lastName: string;
    }): Promise<AuthResponse> => {
      await delay(1000);

      const newUser: User = {
        id: generateId(),
        email: credentials.email,
        firstName: credentials.firstName,
        lastName: credentials.lastName,
        isActive: true,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      return {
        user: newUser,
        tokens: {
          accessToken: 'mock-access-token-' + Date.now(),
          refreshToken: 'mock-refresh-token-' + Date.now(),
        },
      };
    },

    magicLink: async (request: {
      email: string;
    }): Promise<{ message: string }> => {
      await delay(500);
      return { message: `Magic link sent to ${request.email}` };
    },

    refreshToken: async (
      _refreshToken: string
    ): Promise<{ accessToken: string }> => {
      await delay(300);
      return { accessToken: 'mock-new-access-token-' + Date.now() };
    },

    getProfile: async (): Promise<User> => {
      await delay(200);
      return mockUser;
    },
  },

  // Todo endpoints
  todos: {
    getAll: async (params?: {
      page?: number;
      limit?: number;
      search?: string;
      priority?: string;
      completed?: boolean;
    }) => {
      await delay(400);

      let filteredTodos = [...mockTodos];

      // Apply filters
      if (params?.search) {
        const search = params.search.toLowerCase();
        filteredTodos = filteredTodos.filter(
          todo =>
            todo.title.toLowerCase().includes(search) ||
            todo.description?.toLowerCase().includes(search) ||
            todo.tags.some(tag => tag.toLowerCase().includes(search))
        );
      }

      if (params?.priority && params.priority !== 'all') {
        filteredTodos = filteredTodos.filter(
          todo => todo.priority === params.priority
        );
      }

      if (typeof params?.completed === 'boolean') {
        filteredTodos = filteredTodos.filter(
          todo => todo.completed === params.completed
        );
      }

      // Pagination
      const page = params?.page || 1;
      const limit = params?.limit || 10;
      const startIndex = (page - 1) * limit;
      const endIndex = startIndex + limit;
      const paginatedTodos = filteredTodos.slice(startIndex, endIndex);

      return {
        data: paginatedTodos,
        pagination: {
          page,
          limit,
          total: filteredTodos.length,
          totalPages: Math.ceil(filteredTodos.length / limit),
        },
      };
    },

    getById: async (id: string): Promise<Todo> => {
      await delay(200);
      const todo = mockTodos.find(t => t.id === id);
      if (!todo) {
        throw new Error('Todo not found');
      }
      return todo;
    },

    create: async (todoData: CreateTodoRequest): Promise<Todo> => {
      await delay(600);

      const newTodo: Todo = {
        id: generateId(),
        ...todoData,
        completed: false,
        tags: todoData.tags || [],
        userId: mockUser.id,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      mockTodos.unshift(newTodo);
      return newTodo;
    },

    update: async (id: string, updates: UpdateTodoRequest): Promise<Todo> => {
      await delay(400);

      const todoIndex = mockTodos.findIndex(t => t.id === id);
      if (todoIndex === -1) {
        throw new Error('Todo not found');
      }

      const updatedTodo = {
        ...mockTodos[todoIndex],
        ...updates,
        updatedAt: new Date().toISOString(),
      };

      mockTodos[todoIndex] = updatedTodo;
      return updatedTodo;
    },

    delete: async (id: string): Promise<{ message: string }> => {
      await delay(300);

      const todoIndex = mockTodos.findIndex(t => t.id === id);
      if (todoIndex === -1) {
        throw new Error('Todo not found');
      }

      mockTodos.splice(todoIndex, 1);
      return { message: 'Todo deleted successfully' };
    },

    toggle: async (id: string): Promise<Todo> => {
      await delay(200);

      const todoIndex = mockTodos.findIndex(t => t.id === id);
      if (todoIndex === -1) {
        throw new Error('Todo not found');
      }

      const updatedTodo = {
        ...mockTodos[todoIndex],
        completed: !mockTodos[todoIndex].completed,
        updatedAt: new Date().toISOString(),
      };

      mockTodos[todoIndex] = updatedTodo;
      return updatedTodo;
    },

    getStats: async () => {
      await delay(300);

      const total = mockTodos.length;
      const completed = mockTodos.filter(t => t.completed).length;
      const pending = total - completed;
      const overdue = mockTodos.filter(
        t => t.dueDate && new Date(t.dueDate) < new Date() && !t.completed
      ).length;

      const byPriority = mockTodos.reduce(
        (acc, todo) => {
          acc[todo.priority] = (acc[todo.priority] || 0) + 1;
          return acc;
        },
        {} as Record<string, number>
      );

      return {
        total,
        completed,
        pending,
        overdue,
        byPriority,
      };
    },
  },
};

// Export individual endpoints for easier importing
export const { auth: mockAuthApi, todos: mockTodosApi } = mockApi;
