import { useMutation, useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { useAuthContext } from '../context/AuthContext';
import { Tenant, TenantRegisterRequest } from '../types/tenants';
import { queryKeys } from '../lib/queryKeys';
import { TokenResponse } from '../types/auth';
import { AxiosError } from 'axios';

export const useRegisterTenant = () => {
  const { login } = useAuthContext();
  const navigate = useNavigate();

  return useMutation<TokenResponse, AxiosError<{ detail: string }>, TenantRegisterRequest>({
    mutationFn: async (data) => {
      const response = await api.post<TokenResponse>('/tenants/register', data);
      return response.data;
    },
    onSuccess: (data) => {
      login(data.access_token, data.refresh_token);
      navigate('/admin/onboarding');
    },
  });
};

export const useTenantMe = () => {
  const { isAuthenticated, user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery<Tenant, AxiosError<{ detail: string }>>({
    queryKey: queryKeys.tenant.me(tenantId),
    queryFn: async () => {
      const response = await api.get<Tenant>('/tenants/me');
      return response.data;
    },
    enabled: isAuthenticated && !!tenantId,
  });
};

export const useTenantPayNow = () => {
  return useMutation<
    any,
    AxiosError<{ detail: string }>,
    void
  >({
    mutationFn: async () => {
      const response = await api.post('/tenants/me/billing/pay-now');
      return response.data;
    },
  });
};
