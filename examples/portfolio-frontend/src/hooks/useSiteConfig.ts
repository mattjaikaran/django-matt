import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { SiteConfig } from '@/types';

export function useSiteConfig() {
  return useQuery({
    queryKey: ['siteConfig'],
    queryFn: async () => {
      const { data } = await api.get<SiteConfig>('/site-config');
      return data;
    },
  });
}
