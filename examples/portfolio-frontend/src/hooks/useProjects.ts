import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { Project } from '@/types';

export function useProjects(params?: { featured?: boolean }) {
  return useQuery({
    queryKey: ['projects', params],
    queryFn: async () => {
      const { data } = await api.get<Project[]>('/projects', { params });
      return data;
    },
  });
}

export function useProject(slug: string) {
  return useQuery({
    queryKey: ['projects', slug],
    queryFn: async () => {
      const { data } = await api.get<Project>(`/projects/${slug}`);
      return data;
    },
    enabled: !!slug,
  });
}
