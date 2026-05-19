import type { AddToCart, Cart, CartItem } from '@/types';
import { api } from './client';

export const cartApi = {
  getCart: async (): Promise<Cart> => {
    const res = await api.get<Cart>('/cart');
    return res.data;
  },

  addItem: async (data: AddToCart): Promise<CartItem> => {
    const res = await api.post<CartItem>('/cart/items', data);
    return res.data;
  },

  updateItem: async (itemId: string, quantity: number): Promise<CartItem | { detail: string }> => {
    const res = await api.patch<CartItem>(`/cart/items/${itemId}`, { quantity });
    return res.data;
  },

  removeItem: async (itemId: string): Promise<{ detail: string }> => {
    const res = await api.delete<{ detail: string }>(`/cart/items/${itemId}`);
    return res.data;
  },

  clearCart: async (): Promise<{ detail: string }> => {
    const res = await api.delete<{ detail: string }>('/cart');
    return res.data;
  },
};
