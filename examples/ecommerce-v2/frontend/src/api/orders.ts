import type { Order, OrderCreate, OrderStatus, PaginatedResponse } from '@/types';
import { api } from './client';

export const ordersApi = {
  list: async (params?: { status?: OrderStatus; page?: number; pageSize?: number }): Promise<PaginatedResponse<Order>> => {
    const res = await api.get<PaginatedResponse<Order>>('/orders', { params });
    return res.data;
  },

  get: async (orderId: string): Promise<Order> => {
    const res = await api.get<Order>(`/orders/${orderId}`);
    return res.data;
  },

  create: async (data: OrderCreate): Promise<Order> => {
    const res = await api.post<Order>('/orders', data);
    return res.data;
  },

  update: async (orderId: string, data: { status?: OrderStatus; notes?: string }): Promise<Order> => {
    const res = await api.patch<Order>(`/orders/${orderId}`, data);
    return res.data;
  },

  cancel: async (orderId: string): Promise<{ id: string; status: string; detail: string }> => {
    const res = await api.post<{ id: string; status: string; detail: string }>(`/orders/${orderId}/cancel`);
    return res.data;
  },
};
