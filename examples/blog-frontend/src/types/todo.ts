/**
 * Todo-related types
 */

import type { BaseEntity } from './base';

export interface Todo extends BaseEntity {
  title: string;
  description?: string;
  completed: boolean;
  priority: TodoPriority;
  dueDate?: string;
  tags: string[];
  userId: string;
}

export type TodoPriority = 'low' | 'medium' | 'high';

export interface CreateTodoRequest {
  title: string;
  description?: string;
  priority: TodoPriority;
  dueDate?: string;
  tags?: string[];
}

export interface UpdateTodoRequest extends Partial<CreateTodoRequest> {
  completed?: boolean;
}

export interface TodoState {
  todos: Todo[];
  isLoading: boolean;
  error: string | null;
  filters: TodoFilters;
}

export interface TodoFilters {
  search: string;
  priority: TodoPriority | 'all';
  completed: boolean | 'all';
  tags: string[];
}
