import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { Experience } from '@/types';

export function useExperience() {
  return useQuery({
    queryKey: ['experience'],
    queryFn: async () => {
      const { data } = await api.get<Experience[]>('/experience');
      return data;
    },
  });
}
