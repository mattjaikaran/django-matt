import react from '@vitejs/plugin-react';
import path from 'node:path';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
      '@/components': path.resolve(import.meta.dirname, './src/components'),
      '@/routes': path.resolve(import.meta.dirname, './src/routes'),
      '@/forms': path.resolve(import.meta.dirname, './src/forms'),
      '@/lib': path.resolve(import.meta.dirname, './src/lib'),
      '@/hooks': path.resolve(import.meta.dirname, './src/hooks'),
      '@/api': path.resolve(import.meta.dirname, './src/api'),
      '@/types': path.resolve(import.meta.dirname, './src/types'),
      '@/config': path.resolve(import.meta.dirname, './src/config'),
      '@/mock-api': path.resolve(import.meta.dirname, './src/mock-api'),
    },
  },
});
