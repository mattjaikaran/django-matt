import type { PaginatedResponse, Review, ReviewCreate, ReviewSummary } from '@/types';
import { api } from './client';

export const reviewsApi = {
  list: async (productId: string, params?: { limit?: number; offset?: number }): Promise<PaginatedResponse<Review>> => {
    const res = await api.get<PaginatedResponse<Review>>(`/products/${productId}/reviews`, { params });
    return res.data;
  },

  getSummary: async (productId: string): Promise<ReviewSummary> => {
    const res = await api.get<ReviewSummary>(`/products/${productId}/reviews/summary`);
    return res.data;
  },

  create: async (productId: string, data: ReviewCreate): Promise<Review> => {
    const res = await api.post<Review>(`/products/${productId}/reviews`, data);
    return res.data;
  },

  update: async (reviewId: string, data: Partial<ReviewCreate>): Promise<Review> => {
    const res = await api.patch<Review>(`/reviews/${reviewId}`, data);
    return res.data;
  },

  delete: async (reviewId: string): Promise<{ message: string }> => {
    const res = await api.delete<{ message: string }>(`/reviews/${reviewId}`);
    return res.data;
  },
};
