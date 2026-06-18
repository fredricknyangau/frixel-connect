import { RouterStatus } from './routers';

export interface SystemHealth {
  routers: {
    id: string;
    name: string;
    status: RouterStatus;
    last_heartbeat_at: string | null;
  }[];
  queue_depth: number;
  reconciliation_backlog: number;
  webhook_success_rate_24h: number;
}
