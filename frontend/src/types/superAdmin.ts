/**
 * superAdmin.ts
 * Type definitions for all super admin API shapes and domain entities.
 *
 * These types mirror the Pydantic schemas in the FastAPI backend exactly.
 * They are intentionally kept in their own file, separate from types/auth.ts,
 * because super admin auth is an entirely separate flow with different
 * security requirements (TOTP mandatory, no refresh tokens, 15-min expiry).
 */

// ─── Authentication Flow ──────────────────────────────────────────────────────

/**
 * Returned after Step 1 (email + password).
 * This is NOT a usable access token — it only unlocks the TOTP step.
 * The frontend must never store this in localStorage; keep it in memory only.
 */
export interface SuperAdminPreAuthResponse {
  pre_auth_token: string;
  totp_required: boolean;
  /** true on first login — triggers QR code setup flow before verify */
  totp_setup_required: boolean;
}

/**
 * Returned by GET /super-admin/auth/totp-setup when totp_setup_required is true.
 * The QR code is a base64-encoded PNG — render it with <img src={`data:image/png;base64,${qr_code_base64}`} />.
 */
export interface SuperAdminTOTPSetupResponse {
  qr_code_base64: string;
  /** First few characters of the secret, shown as backup text */
  secret_preview: string;
}

/**
 * Returned after Step 2 (pre-auth token + TOTP code).
 * This is the final access token — 15 minutes lifetime, no refresh.
 */
export interface SuperAdminTokenResponse {
  access_token: string;
  token_type: string;
  /** Seconds until expiry — use to display a session countdown */
  expires_in: number;
  super_admin_id: string;
  full_name: string;
}

// ─── Profile ──────────────────────────────────────────────────────────────────

export interface SuperAdminProfile {
  id: string;
  email: string;
  full_name: string;
  /** null until TOTP is verified for the first time */
  totp_verified_at: string | null;
  last_login_at: string | null;
  is_active: boolean;
  created_at: string;
}

// ─── Tenants ──────────────────────────────────────────────────────────────────

/** Subscription tier determines max_customers cap and feature gates */
export type SubscriptionTier = 'starter' | 'growth' | 'scale' | 'enterprise';

/** Lifecycle status of the ISP tenant on the platform */
export type TenantLifecycleStatus = 'active' | 'suspended' | 'cancelled';

/** Billing sub-status — 'grace' means overdue but still running */
export type BillingStatus = 'active' | 'grace' | 'suspended';

/**
 * Lightweight Tenant record used in list views.
 * Full financials and usage counters are deferred to TenantDetail.
 */
export interface Tenant {
  id: string;
  business_name: string;
  owner_email: string;
  owner_phone: string;
  subscription_tier: SubscriptionTier;
  status: TenantLifecycleStatus;
  current_customer_count: number;
  max_customers: number;
  billing_status: BillingStatus;
  next_billing_date: string;
  created_at: string;
}

/**
 * Full tenant record returned by GET /super-admin/tenants/:id.
 * Extends Tenant with aggregated financial and usage metrics.
 */
export interface TenantDetail extends Tenant {
  stats: {
    total_customers: number;
    active_customers: number;
    total_active_routers: number;
    total_active_vouchers: number;
    total_revenue_kes: number;
    last_payment_at: string | null;
  };
}

// ─── Platform Stats ───────────────────────────────────────────────────────────

/**
 * System-wide aggregates shown on the super admin dashboard.
 * These are read-only snapshots — computed on each request by the backend.
 */
export interface PlatformStats {
  total_tenants: number;
  active_tenants: number;
  suspended_tenants: number;
  total_customers_across_all_tenants: number;
  total_revenue_today_kes: number;
  total_revenue_this_month_kes: number;
  total_active_vouchers: number;
  total_active_sessions: number;
  /** Key = tier name (e.g. "starter"), Value = count of tenants on that tier */
  tenants_by_tier: Record<string, number>;
}

// ─── Audit Log ────────────────────────────────────────────────────────────────

/**
 * A single audit log entry.
 * Every super admin action — including reads — is logged.
 * metadata is free-form JSON; shape depends on the action type.
 */
export interface SuperAdminAuditEntry {
  id: string;
  super_admin_id: string;
  super_admin_email: string;
  action: string;
  /** The entity type this action targeted, e.g. "tenant", "super_admin" */
  target_type: string | null;
  /** UUID of the targeted entity */
  target_id: string | null;
  /** Arbitrary JSON blob — e.g. { previous_status, new_status } for suspensions */
  metadata: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

// ─── Impersonation ────────────────────────────────────────────────────────────

/**
 * Returned by POST /super-admin/tenants/:id/impersonate.
 * The impersonation_token grants temporary admin-level access scoped to one tenant.
 * The frontend should NOT store this token in localStorage — use it immediately
 * to open an impersonated session, then discard it.
 */
export interface ImpersonationResponse {
  impersonation_token: string;
  /** ISO 8601 timestamp — show countdown so super admin knows when it expires */
  expires_at: string;
  tenant_name: string;
}
