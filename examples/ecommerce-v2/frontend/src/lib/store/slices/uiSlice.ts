import type { Theme } from '@/types';
import { StateCreator } from 'zustand';

export interface UISlice {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

export const createUISlice: StateCreator<UISlice> = (set) => ({
  theme: 'system',

  setTheme: (theme) => {
    set({ theme });
    localStorage.setItem('theme', theme);
    const root = window.document.documentElement;
    root.classList.remove('light', 'dark');
    if (theme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      root.classList.add(systemTheme);
    } else {
      root.classList.add(theme);
    }
  },
});
