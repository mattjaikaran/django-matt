import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { Skill } from '@/types';

export function useSkills(category?: string) {
  return useQuery({
    queryKey: ['skills', category],
    queryFn: async () => {
      const { data } = await api.get<Skill[]>('/skills', { params: category ? { category } : undefined });
      return data;
    },
  });
}
