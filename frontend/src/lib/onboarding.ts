/**
 * Re-exports onboarding helpers — canonical implementations live in
 * types/onboarding.ts and hooks/useOnboarding.ts.
 */
export type {
  ServiceType,
  OnboardingStep,
  OnboardingState,
  TenantSignupRequest,
} from '../types/onboarding';

export {
  ONBOARDING_STATE_KEY,
  ONBOARDING_SERVICE_KEY,
} from '../types/onboarding';

export {
  getOnboardingState,
  saveOnboardingState,
  clearOnboardingState,
  getServiceType,
  initOnboardingState,
  isOnboardingIncomplete,
  useOnboardingProgress,
} from '../hooks/useOnboarding';

import {
  getOnboardingState,
  saveOnboardingState,
  getServiceType,
} from '../hooks/useOnboarding';
import type { OnboardingState } from '../types/onboarding';

/** @deprecated Use getOnboardingState */
export const readOnboardingState = getOnboardingState;

/** @deprecated Use saveOnboardingState — accepts full state object */
export function writeOnboardingState(state: OnboardingState): void {
  saveOnboardingState(state);
}

/** @deprecated Use getServiceType */
export function getOnboardingServiceType() {
  return getServiceType();
}
