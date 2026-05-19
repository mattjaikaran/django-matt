/**
 * Generic API Hooks
 * Provides type-safe hooks for common API operations using React Query
 */

import { api } from '@/lib/api';
import type { ApiResponse, PaginatedResponse } from '@/types';
import {
  InfiniteData,
  useInfiniteQuery,
  useMutation,
  UseMutationOptions,
  useQuery,
  useQueryClient,
  UseQueryOptions,
} from '@tanstack/react-query';

/**
 * Generic GET hook for fetching data
 */
export const useApiGet = <TData = unknown, TError = Error>(
  url: string,
  options?: Omit<UseQueryOptions<TData, TError>, 'queryKey' | 'queryFn'>
) => {
  return useQuery<TData, TError>({
    queryKey: [url],
    queryFn: async () => {
      const response = await api.get<ApiResponse<TData>>(url);
      return response.data.data;
    },
    ...options,
  });
};

/**
 * Generic GET hook with custom query key
 */
export const useApiQuery = <TData = unknown, TError = Error>(
  queryKey: readonly unknown[],
  url: string,
  options?: Omit<UseQueryOptions<TData, TError>, 'queryKey' | 'queryFn'>
) => {
  return useQuery<TData, TError>({
    queryKey,
    queryFn: async () => {
      const response = await api.get<ApiResponse<TData>>(url);
      return response.data.data;
    },
    ...options,
  });
};

/**
 * Generic POST mutation hook
 */
export const useApiPost = <
  TData = unknown,
  TError = Error,
  TVariables = unknown,
>(
  url: string,
  options?: Omit<UseMutationOptions<TData, TError, TVariables>, 'mutationFn'>
) => {
  return useMutation<TData, TError, TVariables>({
    mutationFn: async (data: TVariables) => {
      const response = await api.post<ApiResponse<TData>>(url, data);
      return response.data.data;
    },
    ...options,
  });
};

/**
 * Generic PUT mutation hook
 */
export const useApiPut = <
  TData = unknown,
  TError = Error,
  TVariables = unknown,
>(
  url: string,
  options?: Omit<UseMutationOptions<TData, TError, TVariables>, 'mutationFn'>
) => {
  return useMutation<TData, TError, TVariables>({
    mutationFn: async (data: TVariables) => {
      const response = await api.put<ApiResponse<TData>>(url, data);
      return response.data.data;
    },
    ...options,
  });
};

/**
 * Generic PATCH mutation hook
 */
export const useApiPatch = <
  TData = unknown,
  TError = Error,
  TVariables = unknown,
>(
  url: string,
  options?: Omit<UseMutationOptions<TData, TError, TVariables>, 'mutationFn'>
) => {
  return useMutation<TData, TError, TVariables>({
    mutationFn: async (data: TVariables) => {
      const response = await api.patch<ApiResponse<TData>>(url, data);
      return response.data.data;
    },
    ...options,
  });
};

/**
 * Generic DELETE mutation hook
 */
export const useApiDelete = <TData = unknown, TError = Error>(
  url: string,
  options?: Omit<UseMutationOptions<TData, TError, void>, 'mutationFn'>
) => {
  return useMutation<TData, TError, void>({
    mutationFn: async () => {
      const response = await api.delete<ApiResponse<TData>>(url);
      return response.data.data;
    },
    ...options,
  });
};

/**
 * Generic DELETE mutation hook with ID parameter
 */
export const useApiDeleteById = <TData = unknown, TError = Error>(
  baseUrl: string,
  options?: Omit<UseMutationOptions<TData, TError, string>, 'mutationFn'>
) => {
  return useMutation<TData, TError, string>({
    mutationFn: async (id: string) => {
      const response = await api.delete<ApiResponse<TData>>(`${baseUrl}/${id}`);
      return response.data.data;
    },
    ...options,
  });
};

/**
 * Infinite query hook for paginated data
 */
export const useApiInfinite = <TData = unknown, TError = Error>(
  queryKey: readonly unknown[],
  url: string
) => {
  return useInfiniteQuery<
    PaginatedResponse<TData>,
    TError,
    InfiniteData<PaginatedResponse<TData>>,
    readonly unknown[],
    number
  >({
    queryKey,
    queryFn: async ({ pageParam }) => {
      const response = await api.get<ApiResponse<PaginatedResponse<TData>>>(
        url,
        {
          params: { page: pageParam },
        }
      );
      return response.data.data;
    },
    initialPageParam: 1,
    getNextPageParam: lastPage => {
      const { page, totalPages } = lastPage.pagination;
      return page < totalPages ? page + 1 : undefined;
    },
  });
};

/**
 * Hook to prefetch data
 */
export const usePrefetch = () => {
  const queryClient = useQueryClient();

  return {
    prefetch: async <TData>(
      queryKey: readonly unknown[],
      queryFn: () => Promise<TData>
    ) => {
      await queryClient.prefetchQuery({
        queryKey,
        queryFn,
      });
    },
    prefetchUrl: async <TData>(queryKey: readonly unknown[], url: string) => {
      await queryClient.prefetchQuery({
        queryKey,
        queryFn: async () => {
          const response = await api.get<ApiResponse<TData>>(url);
          return response.data.data;
        },
      });
    },
  };
};

/**
 * Hook to invalidate queries
 */
export const useInvalidate = () => {
  const queryClient = useQueryClient();

  return {
    invalidate: (queryKey: readonly unknown[]) =>
      queryClient.invalidateQueries({ queryKey }),
    invalidateAll: () => queryClient.invalidateQueries(),
    invalidateExact: (queryKey: readonly unknown[]) =>
      queryClient.invalidateQueries({ queryKey, exact: true }),
    remove: (queryKey: readonly unknown[]) =>
      queryClient.removeQueries({ queryKey }),
  };
};
