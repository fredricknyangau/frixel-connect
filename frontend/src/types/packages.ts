import type { ServiceType } from './onboarding';

export interface Package {
  id: string;
  name: string;
  description: string;
  price_kes: number;
  duration_minutes: number;
  speed_mbps: number;
  is_active: boolean;
  created_at: string;
  /** Present once backend adds package_type; until then resolved client-side. */
  service_type?: ServiceType;
}

export interface PackageCreateRequest {
  name: string;
  description: string;
  price_kes: number;
  duration_minutes: number;
  speed_mbps: number;
  service_type?: ServiceType;
}
