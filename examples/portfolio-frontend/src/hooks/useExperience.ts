import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { Experience, PaginatedResponse } from '@/types';

export function useExperience(params?: { limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ['experience', params],
    queryFn: async () => {
      const { data } = await api.get<PaginatedResponse<Experience>>('/experience', { params });
      return data;
    },
  });
}
