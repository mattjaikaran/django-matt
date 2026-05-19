import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { Skill, PaginatedResponse } from '@/types';

export function useSkills() {
  return useQuery({
    queryKey: ['skills'],
    queryFn: async () => {
      const { data } = await api.get<PaginatedResponse<Skill>>('/skills');
      return data;
    },
  });
}
