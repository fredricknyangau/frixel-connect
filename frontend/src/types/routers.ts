import type { ServiceType } from './onboarding';

export type RouterStatus = 'online' | 'offline' | 'unknown' | 'pending_setup' | 'testing';

export interface MikrotikRouter {
  id: string;
  name: string;
  host: string | null;
  port: number | null;
  username: string | null;
  site_name: string;
  status: RouterStatus;
  last_heartbeat_at: string | null;
  created_at: string;
  wireguard_public_key: string | null;
  wireguard_assigned_ip: string | null;
  wireguard_peer_public_key: string | null;
  /** TODO: Backend should return provisioned service type (hotspot vs pppoe). */
  service_type?: ServiceType;
}

export interface RouterCreateRequest {
  name: string;
  host: string;
  port: number;
  username: string;
  password?: string;
  site_name: string;
}
