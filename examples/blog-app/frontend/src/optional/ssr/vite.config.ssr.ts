/**
 * Vite SSR Configuration
 * This config is used when building for SSR
 */

import { tanstackRouter } from '@tanstack/router-plugin/vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { defineConfig } from 'vite';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    tanstackRouter({
      target: 'react',
      autoCodeSplitting: true,
    }),
    react(),
  ],
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
  build: {
    ssr: true,
  },
  ssr: {
    // Externalize deps that shouldn't be bundled for SSR
    external: ['react', 'react-dom'],
    // Don't externalize these - they need to be bundled
    noExternal: [
      '@tanstack/react-router',
      '@tanstack/react-query',
      'zustand',
      /^@radix-ui\/.*/,
    ],
  },
});
