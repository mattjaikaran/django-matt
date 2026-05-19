import type { SearchResponse } from '@/types';
import { api } from './client';

export const searchApi = {
  search: async (params: {
    q?: string;
    category?: string;
    minPrice?: number;
    maxPrice?: number;
    limit?: number;
    offset?: number;
  }): Promise<SearchResponse> => {
    const res = await api.get<SearchResponse>('/search', { params });
    return res.data;
  },
};
