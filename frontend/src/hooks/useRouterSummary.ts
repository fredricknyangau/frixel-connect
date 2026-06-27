import { useQuery } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { api } from '../lib/api';
import { queryKeys } from '../lib/queryKeys';
import { useAuthContext } from '../context/AuthContext';
import { MikrotikRouter } from '../types/routers';
import type { ServiceType } from '../types/onboarding';

export interface RouterSummary {
  hasHotspotRouter: boolean;
  hasPPPoERouter: boolean;
  hasOnlineRouter: boolean;
  routers: MikrotikRouter[];
  isLoading: boolean;
}

export function resolveRouterServiceType(router: MikrotikRouter): ServiceType {
  if (router.service_type === 'pppoe') return 'pppoe';
  if (router.service_type === 'hotspot') return 'hotspot';
  return 'hotspot';
}

function summariseRouters(routers: MikrotikRouter[]): Omit<RouterSummary, 'isLoading'> {
  let hasHotspotRouter = false;
  let hasPPPoERouter = false;
  let hasOnlineRouter = false;

  for (const router of routers) {
    const serviceType = resolveRouterServiceType(router);
    if (serviceType === 'pppoe') hasPPPoERouter = true;
    else hasHotspotRouter = true;
    if (router.status === 'online') hasOnlineRouter = true;
  }

  return { hasHotspotRouter, hasPPPoERouter, hasOnlineRouter, routers };
}

export function useRouterSummary(): RouterSummary {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  const { data, isLoading } = useQuery<MikrotikRouter[], AxiosError<{ detail: string }>>({
    queryKey: queryKeys.routers.all(tenantId),
    queryFn: async () => {
      const response = await api.get<MikrotikRouter[]>('/admin/routers');
      return response.data;
    },
    enabled: !!tenantId,
    staleTime: 5 * 60 * 1000,
  });

  const routers = data ?? [];
  const summary = summariseRouters(routers);

  return { ...summary, isLoading };
}
