import { Link } from 'react-router-dom';
import { formatDistanceToNow, parseISO } from 'date-fns';
import { Wifi } from 'lucide-react';
import { RouterStatusBadge } from '../shared/RouterStatusBadge';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Skeleton } from '../ui/skeleton';
import { cn } from '../../lib/utils';
import type { MikrotikRouter, RouterStatus } from '../../types/routers';

/** Map raw router status to dashboard health colours (degraded = amber). */
export function getRouterHealthStatus(status: RouterStatus): 'online' | 'degraded' | 'offline' {
  if (status === 'online') return 'online';
  if (status === 'offline') return 'offline';
  return 'degraded';
}

const healthBorderClass: Record<'online' | 'degraded' | 'offline', string> = {
  online: 'border-l-transparent',
  degraded: 'border-l-amber-500',
  offline: 'border-l-red-500',
};

function formatLastSeen(lastHeartbeat: string | null): string {
  if (!lastHeartbeat) return 'Never connected';
  try {
    return `Last seen ${formatDistanceToNow(parseISO(lastHeartbeat), { addSuffix: false })} ago`;
  } catch {
    return 'Last seen unknown';
  }
}

interface RouterStatusWidgetProps {
  routers: MikrotikRouter[];
  isLoading: boolean;
}

/** Persistent infrastructure health panel — always visible on the admin dashboard. */
export function RouterStatusWidget({ routers, isLoading }: RouterStatusWidgetProps) {
  const hasOffline = routers.some((r) => getRouterHealthStatus(r.status) === 'offline');

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-base font-semibold flex items-center gap-2">
          <Wifi className="h-4 w-4 text-primary" />
          Router health
        </CardTitle>
        {hasOffline && (
          <Link to="/admin/routers" className="text-sm text-destructive hover:underline">
            Check routers
          </Link>
        )}
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading ? (
          Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-md" />
          ))
        ) : routers.length === 0 ? (
          <div className="flex flex-col gap-2 rounded-md border border-dashed p-4 text-sm text-muted-foreground">
            <span>No routers connected</span>
            <Link
              to="/admin/onboarding/router"
              className="inline-flex h-7 w-fit items-center rounded-lg border border-border bg-background px-2.5 text-sm hover:bg-muted"
            >
              Connect router →
            </Link>
          </div>
        ) : (
          routers.map((router) => {
            const health = getRouterHealthStatus(router.status);
            return (
              <div
                key={router.id}
                className={cn(
                  'flex items-center justify-between gap-3 rounded-md border border-l-4 bg-muted/30 px-3 py-2.5',
                  healthBorderClass[health],
                )}
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">
                    {router.name}
                    <span className="text-muted-foreground font-normal"> · {router.site_name}</span>
                  </p>
                  <p className="text-xs text-muted-foreground">{formatLastSeen(router.last_heartbeat_at)}</p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {health === 'offline' && (
                    <Link
                      to="/admin/routers"
                      className="text-xs text-destructive hover:underline"
                    >
                      Check router
                    </Link>
                  )}
                  <RouterStatusBadge
                    status={health === 'degraded' ? 'pending_setup' : router.status}
                    className={
                      health === 'degraded'
                        ? 'bg-amber-100 text-amber-800 hover:bg-amber-100'
                        : undefined
                    }
                  />
                </div>
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
