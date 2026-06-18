export type RouterStatus = 'online' | 'offline' | 'unknown';

export interface MikrotikRouter {
  id: string;
  name: string;
  host: string;
  port: number;
  site_name: string;
  status: RouterStatus;
  last_heartbeat_at: string | null;
  created_at: string;
}

export interface RouterCreateRequest {
  name: string;
  host: string;
  port: number;
  username: string;
  password?: string;
  site_name: string;
}
