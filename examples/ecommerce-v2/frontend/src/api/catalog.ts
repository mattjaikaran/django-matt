import type { Category, PaginatedResponse, Product, ProductCreate, ProductUpdate, Variant } from '@/types';
import { api } from './client';

export const catalogApi = {
  // Categories
  listCategories: async (params?: { parent?: string }): Promise<PaginatedResponse<Category>> => {
    const res = await api.get<PaginatedResponse<Category>>('/categories', { params });
    return res.data;
  },

  getCategory: async (id: string): Promise<Category> => {
    const res = await api.get<Category>(`/categories/${id}`);
    return res.data;
  },

  // Products
  listProducts: async (params?: {
    category?: string;
    store?: string;
    minPrice?: number;
    maxPrice?: number;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<PaginatedResponse<Product>> => {
    const res = await api.get<PaginatedResponse<Product>>('/products', { params });
    return res.data;
  },

  getProduct: async (productId: string): Promise<Product> => {
    const res = await api.get<Product>(`/products/${productId}`);
    return res.data;
  },

  createProduct: async (data: ProductCreate): Promise<Product> => {
    const res = await api.post<Product>('/products', data);
    return res.data;
  },

  updateProduct: async (productId: string, data: ProductUpdate): Promise<Product> => {
    const res = await api.patch<Product>(`/products/${productId}`, data);
    return res.data;
  },

  deleteProduct: async (productId: string): Promise<{ message: string }> => {
    const res = await api.delete<{ message: string }>(`/products/${productId}`);
    return res.data;
  },

  // Variants
  listVariants: async (productId: string): Promise<PaginatedResponse<Variant>> => {
    const res = await api.get<PaginatedResponse<Variant>>(`/products/${productId}/variants`);
    return res.data;
  },
};
