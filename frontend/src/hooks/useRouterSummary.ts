import { useQuery } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { api } from '../lib/api';
import { MikrotikRouter } from '../types/routers';
import type { ServiceType } from '../types/onboarding';

export interface RouterSummary {
  hasHotspotRouter: boolean;
  hasPPPoERouter: boolean;
  hasOnlineRouter: boolean;
  routers: MikrotikRouter[];
  isLoading: boolean;
}

/**
 * Resolve router service type for sidebar / customer badges.
 * TODO: Remove fallback once GET /admin/routers includes service_type per router.
 */
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

/** Cached router list with service-type flags for sidebar and dashboard widgets. */
export function useRouterSummary(): RouterSummary {
  const { data, isLoading } = useQuery<MikrotikRouter[], AxiosError<{ detail: string }>>({
    queryKey: ['routers'],
    queryFn: async () => {
      const response = await api.get<MikrotikRouter[]>('/admin/routers');
      return response.data;
    },
    staleTime: 5 * 60 * 1000,
  });

  const routers = data ?? [];
  const summary = summariseRouters(routers);

  return { ...summary, isLoading };
}
