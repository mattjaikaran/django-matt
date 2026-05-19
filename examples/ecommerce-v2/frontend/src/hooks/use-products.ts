import { catalogApi } from '@/api/catalog';
import { useQuery } from '@tanstack/react-query';

export const useProducts = (params?: {
  category?: string;
  store?: string;
  minPrice?: number;
  maxPrice?: number;
  search?: string;
  limit?: number;
  offset?: number;
}) => useQuery({
  queryKey: ['products', params],
  queryFn: () => catalogApi.listProducts(params),
});

export const useProduct = (productId: string) => useQuery({
  queryKey: ['products', productId],
  queryFn: () => catalogApi.getProduct(productId),
  enabled: !!productId,
});

export const useCategories = (params?: { parent?: string }) => useQuery({
  queryKey: ['categories', params],
  queryFn: () => catalogApi.listCategories(params),
});

export const useVariants = (productId: string) => useQuery({
  queryKey: ['variants', productId],
  queryFn: () => catalogApi.listVariants(productId),
  enabled: !!productId,
});
