/**
 * In the backend, Pydantic schemas are the contract between layers. 
 * In the frontend, these TypeScript types are the exact same thing —
 * they make the API contract explicit and compiler-enforced.
 */

export type UserRole = 'admin' | 'reseller' | 'customer';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  phone: string;
  password: string;
  role: UserRole;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: UserRole;
  user_id: string;
}

export interface DecodedToken {
  sub: string;
  role: UserRole;
  reseller_id: string | null;
  exp: number;
  iat: number;
}
