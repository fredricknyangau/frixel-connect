import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { api } from '../lib/api';
import { useAuthContext } from '../context/AuthContext';
import { Tenant } from '../types/tenants';
import { initOnboardingState, ServiceType } from '../lib/onboarding';

export interface TenantSignupRequest {
  business_name: string;
  owner_name: string;
  owner_email: string;
  owner_phone: string;
  password: string;
  subscription_tier: 'starter' | 'growth' | 'scale' | 'enterprise';
  service_type: ServiceType;
}

interface TenantRegisterApiBody {
  business_name: string;
  owner_email: string;
  owner_phone: string;
  password: string;
  subscription_tier: string;
}

interface TenantRegisterResponse {
  tenant: Tenant;
  access_token: string;
  token_type: string;
  user_id: string;
}

/**
 * Tenant signup mutation. service_type and owner_name are collected in the form
 * but NOT sent to POST /tenants/register — the backend schema does not include
 * them yet. service_type is stored in localStorage for the onboarding wizard;
 * owner_name is reserved for future profile enrichment.
 */
export function useTenantSignup() {
  const { login } = useAuthContext();
  const navigate = useNavigate();

  return useMutation<
    TenantRegisterResponse,
    AxiosError<{ detail?: string | Array<{ loc: (string | number)[]; msg: string }> }>,
    TenantSignupRequest
  >({
    mutationFn: async (data) => {
      const body: TenantRegisterApiBody = {
        business_name: data.business_name,
        owner_email: data.owner_email,
        owner_phone: data.owner_phone.replace(/\s+/g, ''),
        password: data.password,
        subscription_tier: data.subscription_tier,
      };
      const response = await api.post<TenantRegisterResponse>('/tenants/register', body);
      return response.data;
    },
    onSuccess: (data, variables) => {
      // Register endpoint returns access_token only (no refresh_token).
      login(data.access_token, '');
      initOnboardingState(variables.service_type);
      navigate('/admin/onboarding');
    },
  });
}
