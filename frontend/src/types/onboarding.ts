/** Service line chosen at signup-drives onboarding defaults and admin UI copy. */
export type ServiceType = 'hotspot' | 'pppoe';

/** Steps in the post-signup onboarding shell. */
export type OnboardingStep = 'packages' | 'router' | 'complete';

/** Persisted in localStorage so onboarding survives browser refresh. */
export interface OnboardingState {
  step: OnboardingStep;
  packages_done: boolean;
  router_done: boolean;
  router_id: string | null;
  package_id: string | null;
  /** Extra display fields kept for step-3 summary (not in original spec but used by OnboardingPage). */
  router_name?: string | null;
  package_name?: string | null;
  service_type: ServiceType;
  started_at: string;
}

/** Public tenant signup payload-service_type is stored client-side until backend accepts it. */
export interface TenantSignupRequest {
  business_name: string;
  owner_name: string;
  owner_email: string;
  owner_phone: string;
  password: string;
  subscription_tier: 'starter' | 'growth' | 'scale' | 'enterprise';
}

export const ONBOARDING_STATE_KEY = 'Frixel Connect_onboarding_state';
export const ONBOARDING_SERVICE_KEY = 'Frixel Connect_onboarding_service';
