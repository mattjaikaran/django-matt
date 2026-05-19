import { generateId } from '@/lib/utils';
import type { Notification, Theme, UIState } from '@/types';
import { StateCreator } from 'zustand';

export interface UISlice extends UIState {
  // Theme actions
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;

  // Sidebar actions
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;

  // Notification actions
  addNotification: (
    notification: Omit<Notification, 'id' | 'createdAt'>
  ) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;
}

const initialState: UIState = {
  theme: 'system',
  sidebarOpen: false,
  notifications: [],
};

export const createUISlice: StateCreator<UISlice> = (set, get) => ({
  ...initialState,

  setTheme: (theme: Theme) => {
    set({ theme });
    localStorage.setItem('theme', theme);

    // Apply theme to document
    const root = window.document.documentElement;
    root.classList.remove('light', 'dark');

    if (theme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)')
        .matches
        ? 'dark'
        : 'light';
      root.classList.add(systemTheme);
    } else {
      root.classList.add(theme);
    }
  },

  toggleTheme: () => {
    const { theme, setTheme } = get();
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
  },

  setSidebarOpen: (sidebarOpen: boolean) => {
    set({ sidebarOpen });
  },

  toggleSidebar: () => {
    const { sidebarOpen } = get();
    set({ sidebarOpen: !sidebarOpen });
  },

  addNotification: notificationData => {
    const { notifications } = get();
    const notification: Notification = {
      ...notificationData,
      id: generateId(),
      createdAt: new Date().toISOString(),
    };

    set({
      notifications: [notification, ...notifications],
    });

    // Auto-remove notification after duration (default 5 seconds)
    const duration = notification.duration || 5000;
    if (duration > 0) {
      setTimeout(() => {
        get().removeNotification(notification.id);
      }, duration);
    }
  },

  removeNotification: (id: string) => {
    const { notifications } = get();
    set({
      notifications: notifications.filter(n => n.id !== id),
    });
  },

  clearNotifications: () => {
    set({ notifications: [] });
  },
});
