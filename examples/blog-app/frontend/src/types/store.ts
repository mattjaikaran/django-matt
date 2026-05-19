/**
 * Store-related types
 */

import type { AuthState } from './auth';
import type { TodoState } from './todo';
import type { UIState } from './ui';

export interface StoreState {
  auth: AuthState;
  todos: TodoState;
  ui: UIState;
}
