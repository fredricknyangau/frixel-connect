export interface Package {
  id: string;
  name: string;
  description: string;
  price_kes: number;
  duration_days: number;
  speed_mbps: number;
  is_active: boolean;
  created_at: string;
}

export interface PackageCreateRequest {
  name: string;
  description: string;
  price_kes: number;
  duration_days: number;
  speed_mbps: number;
}
