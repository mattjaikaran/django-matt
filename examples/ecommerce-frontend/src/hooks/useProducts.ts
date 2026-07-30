import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { Product } from '@/types';

export function useProducts(category?: string, search?: string) {
  return useQuery({
    queryKey: ['products', { category, search }],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (category) params.set('category', category);
      if (search) params.set('search', search);
      const { data } = await api.get<Product[]>(`/products/?${params.toString()}`);
      return data;
    },
  });
}

export function useProduct(id: string) {
  return useQuery({
    queryKey: ['products', id],
    queryFn: async () => {
      const { data } = await api.get<Product>(`/products/${id}/`);
      return data;
    },
    enabled: !!id,
  });
}
