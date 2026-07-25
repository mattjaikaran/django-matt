import type { AuthState } from './auth';
import type { UIState } from './ui';

export interface StoreState {
  auth: AuthState;
  ui: UIState;
}
