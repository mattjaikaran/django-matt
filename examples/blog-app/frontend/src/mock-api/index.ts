import type { AuthResponse, User } from '@/types';

const mockUser: User = {
  id: '1',
  email: 'demo@example.com',
  firstName: 'Demo',
  lastName: 'User',
  isActive: true,
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-01T00:00:00Z',
};

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
const generateId = () => Math.random().toString(36).substr(2, 9);

export const mockApi = {
  auth: {
    login: async (credentials: {
      email: string;
      password: string;
    }): Promise<AuthResponse> => {
      await delay(800);

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
};

export const { auth: mockAuthApi } = mockApi;
