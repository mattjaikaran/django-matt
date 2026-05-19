/**
 * Config Slice - Application configuration state
 * Uses Zustand instead of React Context for better performance
 */

import type { AppConfig } from '@/config';
import { config as defaultConfig } from '@/config';
import type { StateCreator } from 'zustand';

export interface ConfigSlice {
  // State
  config: AppConfig;

  // Computed
  isDjangoSPA: boolean;
  isStandalone: boolean;

  // Actions
  updateConfig: (updates: Partial<AppConfig>) => void;
  isFeatureEnabled: (feature: keyof AppConfig['features']) => boolean;
  setFeature: (feature: keyof AppConfig['features'], enabled: boolean) => void;
}

export const createConfigSlice: StateCreator<ConfigSlice> = (set, get) => ({
  // Initial state from config
  config: defaultConfig,
  isDjangoSPA: defaultConfig.env.mode === 'django-spa',
  isStandalone: defaultConfig.env.mode === 'standalone',

  updateConfig: (updates: Partial<AppConfig>) => {
    const { config } = get();
    const newConfig = { ...config, ...updates };
    set({
      config: newConfig,
      isDjangoSPA: newConfig.env.mode === 'django-spa',
      isStandalone: newConfig.env.mode === 'standalone',
    });
  },

  isFeatureEnabled: (feature: keyof AppConfig['features']) => {
    const { config } = get();
    return config.features[feature];
  },

  setFeature: (feature: keyof AppConfig['features'], enabled: boolean) => {
    const { config, updateConfig } = get();
    updateConfig({
      features: {
        ...config.features,
        [feature]: enabled,
      },
    });
  },
});
