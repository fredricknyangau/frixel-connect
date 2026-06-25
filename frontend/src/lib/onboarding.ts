/**
 * Onboarding state persisted in localStorage across signup → package → router → dashboard.
 * service_type is chosen at signup and drives package form defaults in step 1.
 */

export type ServiceType = 'hotspot' | 'pppoe';

export type OnboardingStep = 'packages' | 'router' | 'complete';

export interface OnboardingState {
  step: OnboardingStep;
  packages_done: boolean;
  router_done: boolean;
  router_id: string | null;
  router_name: string | null;
  package_id: string | null;
  package_name: string | null;
  service_type: ServiceType;
  started_at: string;
}

export const ONBOARDING_SERVICE_KEY = 'zealsync_onboarding_service';
export const ONBOARDING_STATE_KEY = 'zealsync_onboarding_state';

export function getOnboardingServiceType(): ServiceType {
  const stored = localStorage.getItem(ONBOARDING_SERVICE_KEY);
  return stored === 'pppoe' ? 'pppoe' : 'hotspot';
}

export function readOnboardingState(): OnboardingState | null {
  const raw = localStorage.getItem(ONBOARDING_STATE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as OnboardingState;
  } catch {
    return null;
  }
}

export function writeOnboardingState(state: OnboardingState): void {
  localStorage.setItem(ONBOARDING_STATE_KEY, JSON.stringify(state));
}

export function initOnboardingState(serviceType: ServiceType): OnboardingState {
  const state: OnboardingState = {
    step: 'packages',
    packages_done: false,
    router_done: false,
    router_id: null,
    router_name: null,
    package_id: null,
    package_name: null,
    service_type: serviceType,
    started_at: new Date().toISOString(),
  };
  localStorage.setItem(ONBOARDING_SERVICE_KEY, serviceType);
  writeOnboardingState(state);
  return state;
}

export function clearOnboardingState(): void {
  localStorage.removeItem(ONBOARDING_STATE_KEY);
  localStorage.removeItem(ONBOARDING_SERVICE_KEY);
}

export function isOnboardingIncomplete(): boolean {
  const state = readOnboardingState();
  if (!state) return false;
  return state.step !== 'complete';
}
