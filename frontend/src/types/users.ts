import { UserRole } from './auth';

export interface User {
  id: string;
  email: string;
  phone: string;
  role: UserRole;
  reseller_id: string | null;
  is_active: boolean;
  created_at: string;
}

export interface UserUpdateRequest {
  email?: string;
  phone?: string;
}

export interface CustomerCreateRequest {
  email: string;
  phone: string;
  password: string;
}
