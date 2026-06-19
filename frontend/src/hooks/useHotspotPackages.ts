import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Package } from '../types/packages';

export function useHotspotPackages(tenantId: string | null) {
  return useQuery({
    queryKey: ['hotspot-packages', tenantId],
    queryFn: async () => {
      if (!tenantId) return [];
      // This endpoint is public (no JWT needed) but requires tenant_id
      const response = await api.get<Package[]>(`/hotspot/packages`, {
        params: { tenant_id: tenantId }
      });
      return response.data;
    },
    enabled: !!tenantId,
    staleTime: 5 * 60 * 1000,
  });
}
