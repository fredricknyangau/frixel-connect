import { useSyncExternalStore } from 'react';
import {
  ONBOARDING_SERVICE_KEY,
  ONBOARDING_STATE_KEY,
  type OnboardingState,
  type ServiceType,
} from '../types/onboarding';

const DEFAULT_STATE: OnboardingState = {
  step: 'packages',
  packages_done: false,
  router_done: false,
  router_id: null,
  package_id: null,
  service_type: 'hotspot',
  started_at: new Date().toISOString(),
};

/** Read persisted onboarding state; returns null when missing or corrupt. */
export function getOnboardingState(): OnboardingState | null {
  const raw = localStorage.getItem(ONBOARDING_STATE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as OnboardingState;
  } catch {
    return null;
  }
}

/** Merge partial updates into existing onboarding state. */
export function saveOnboardingState(partial: Partial<OnboardingState>): void {
  const existing = getOnboardingState() ?? DEFAULT_STATE;
  const merged: OnboardingState = { ...existing, ...partial };
  localStorage.setItem(ONBOARDING_STATE_KEY, JSON.stringify(merged));
  window.dispatchEvent(new Event('zealsync-onboarding-change'));
}

/** Clear onboarding progress after go-live. */
export function clearOnboardingState(): void {
  localStorage.removeItem(ONBOARDING_STATE_KEY);
  localStorage.removeItem(ONBOARDING_SERVICE_KEY);
  window.dispatchEvent(new Event('zealsync-onboarding-change'));
}

/** Service type from onboarding state, falling back to dedicated key then hotspot. */
export function getServiceType(): ServiceType {
  const fromState = getOnboardingState()?.service_type;
  if (fromState) return fromState;
  const stored = localStorage.getItem(ONBOARDING_SERVICE_KEY);
  return stored === 'pppoe' ? 'pppoe' : 'hotspot';
}

function subscribeOnboarding(callback: () => void): () => void {
  const handler = () => callback();
  window.addEventListener('storage', handler);
  window.addEventListener('zealsync-onboarding-change', handler);
  return () => {
    window.removeEventListener('storage', handler);
    window.removeEventListener('zealsync-onboarding-change', handler);
  };
}

/** Reactive slice of onboarding progress for shell UI. */
export function useOnboardingProgress() {
  const state = useSyncExternalStore(
    subscribeOnboarding,
    () => getOnboardingState(),
    () => null,
  );

  return {
    step: state?.step ?? 'packages',
    packages_done: state?.packages_done ?? false,
    router_done: state?.router_done ?? false,
    service_type: state?.service_type ?? getServiceType(),
  };
}

/** Initialise onboarding after signup-writes both service key and full state. */
export function initOnboardingState(serviceType: ServiceType): OnboardingState {
  const state: OnboardingState = {
    ...DEFAULT_STATE,
    service_type: serviceType,
    started_at: new Date().toISOString(),
  };
  localStorage.setItem(ONBOARDING_SERVICE_KEY, serviceType);
  localStorage.setItem(ONBOARDING_STATE_KEY, JSON.stringify(state));
  window.dispatchEvent(new Event('zealsync-onboarding-change'));
  return state;
}

export function isOnboardingIncomplete(): boolean {
  const state = getOnboardingState();
  if (!state) return false;
  return state.step !== 'complete';
}
