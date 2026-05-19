import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { createAuthSlice, type AuthSlice } from './slices/authSlice';
import { createCartSlice, type CartSlice } from './slices/cartSlice';
import { createUISlice, type UISlice } from './slices/uiSlice';

export type AppStore = AuthSlice & CartSlice & UISlice;

export const useStore = create<AppStore>()(
  devtools(
    (...args) => ({
      ...createAuthSlice(...args),
      ...createCartSlice(...args),
      ...createUISlice(...args),
    }),
    { name: 'ecommerce-store' }
  )
);

export const useAuth = () =>
  useStore(state => ({
    user: state.user,
    tokens: state.tokens,
    isAuthenticated: state.isAuthenticated,
    isLoading: state.isLoading,
    login: state.login,
    register: state.register,
    logout: state.logout,
    setUser: state.setUser,
    initializeAuth: state.initializeAuth,
  }));

export const useCartStore = () =>
  useStore(state => ({
    cart: state.cart,
    cartOpen: state.cartOpen,
    setCart: state.setCart,
    setCartOpen: state.setCartOpen,
    optimisticAddItem: state.optimisticAddItem,
    optimisticRemoveItem: state.optimisticRemoveItem,
    clearLocalCart: state.clearLocalCart,
  }));

export const useUI = () =>
  useStore(state => ({
    theme: state.theme,
    setTheme: state.setTheme,
  }));

export const initializeStore = () => {
  const { initializeAuth, setTheme } = useStore.getState();
  initializeAuth();
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme === 'light' || savedTheme === 'dark' || savedTheme === 'system') {
    setTheme(savedTheme);
  }
};
