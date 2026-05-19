/**
 * UI-related types
 */

import type { Theme } from './base';

export interface UIState {
  theme: Theme;
  sidebarOpen: boolean;
  notifications: Notification[];
}

export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
  createdAt: string;
}
