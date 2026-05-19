import type { Cart, CartItem } from '@/types';
import { StateCreator } from 'zustand';

export interface CartSlice {
  cart: Cart | null;
  cartOpen: boolean;
  setCart: (cart: Cart | null) => void;
  setCartOpen: (open: boolean) => void;
  optimisticAddItem: (item: CartItem) => void;
  optimisticRemoveItem: (itemId: string) => void;
  clearLocalCart: () => void;
}

export const createCartSlice: StateCreator<CartSlice> = (set, get) => ({
  cart: null,
  cartOpen: false,

  setCart: (cart) => set({ cart }),
  setCartOpen: (cartOpen) => set({ cartOpen }),

  optimisticAddItem: (item) => {
    const { cart } = get();
    if (!cart) return;
    const existing = cart.items.find(i => i.id === item.id);
    const items = existing
      ? cart.items.map(i => i.id === item.id ? { ...i, quantity: i.quantity + item.quantity } : i)
      : [...cart.items, item];
    set({ cart: { ...cart, items, itemCount: items.reduce((s, i) => s + i.quantity, 0) } });
  },

  optimisticRemoveItem: (itemId) => {
    const { cart } = get();
    if (!cart) return;
    const items = cart.items.filter(i => i.id !== itemId);
    set({ cart: { ...cart, items, itemCount: items.reduce((s, i) => s + i.quantity, 0) } });
  },

  clearLocalCart: () => set({ cart: null }),
});
