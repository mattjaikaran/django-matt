import type { PaginatedResponse, Store, StoreCreate, StoreUpdate } from '@/types';
import { api } from './client';

export const storesApi = {
  list: async (params?: { search?: string; limit?: number; offset?: number }): Promise<PaginatedResponse<Store>> => {
    const res = await api.get<PaginatedResponse<Store>>('/stores', { params });
    return res.data;
  },

  get: async (storeId: string): Promise<Store> => {
    const res = await api.get<Store>(`/stores/${storeId}`);
    return res.data;
  },

  create: async (data: StoreCreate): Promise<Store> => {
    const res = await api.post<Store>('/stores', data);
    return res.data;
  },

  update: async (storeId: string, data: StoreUpdate): Promise<Store> => {
    const res = await api.patch<Store>(`/stores/${storeId}`, data);
    return res.data;
  },

  delete: async (storeId: string): Promise<{ message: string }> => {
    const res = await api.delete<{ message: string }>(`/stores/${storeId}`);
    return res.data;
  },
};
