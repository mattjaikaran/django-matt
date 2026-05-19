/**
 * Server Actions Pattern
 *
 * This module provides patterns for server actions that can be used
 * with SSR or migrated to RSC-enabled frameworks.
 *
 * In Vite with SSR:
 * - These functions run during SSR on the server
 * - On client navigation, they trigger API calls
 *
 * In Next.js with RSC:
 * - Mark these with 'use server' directive
 * - They become true server actions
 */

import { authApi } from '@/api/auth';
import { todosApi } from '@/api/todos';
import type {
  CreateTodoRequest,
  LoginCredentials,
  RegisterCredentials,
  Todo,
  UpdateTodoRequest,
} from '@/types';

/**
 * Server action type definition
 */
export type ServerAction<TInput, TOutput> = (input: TInput) => Promise<TOutput>;

/**
 * Create a form action wrapper
 * Converts a server action to work with form submissions
 */
export function createFormAction<TInput, TOutput>(
  action: ServerAction<TInput, TOutput>
) {
  return async (formData: FormData): Promise<TOutput> => {
    const data = Object.fromEntries(formData.entries()) as unknown as TInput;
    return action(data);
  };
}

// ============================================
// Todo Server Actions
// ============================================

export const createTodoAction: ServerAction<
  CreateTodoRequest,
  Todo
> = async data => {
  return todosApi.createTodo(data);
};

export const updateTodoAction: ServerAction<
  { id: string; updates: UpdateTodoRequest },
  Todo
> = async ({ id, updates }) => {
  return todosApi.updateTodo(id, updates);
};

export const deleteTodoAction: ServerAction<
  string,
  { message: string }
> = async id => {
  return todosApi.deleteTodo(id);
};

export const toggleTodoAction: ServerAction<string, Todo> = async id => {
  return todosApi.toggleTodo(id);
};

// ============================================
// Auth Server Actions
// ============================================

export const loginAction: ServerAction<
  LoginCredentials,
  { success: boolean }
> = async credentials => {
  try {
    await authApi.login(credentials);
    return { success: true };
  } catch {
    return { success: false };
  }
};

export const registerAction: ServerAction<
  RegisterCredentials,
  { success: boolean }
> = async credentials => {
  try {
    await authApi.register(credentials);
    return { success: true };
  } catch {
    return { success: false };
  }
};

export const logoutAction: ServerAction<
  void,
  { success: boolean }
> = async () => {
  try {
    await authApi.logout();
    return { success: true };
  } catch {
    return { success: false };
  }
};

// ============================================
// Form Action Wrappers
// ============================================

export const createTodoFormAction = createFormAction(createTodoAction);
export const loginFormAction = createFormAction(loginAction);
export const registerFormAction = createFormAction(registerAction);
