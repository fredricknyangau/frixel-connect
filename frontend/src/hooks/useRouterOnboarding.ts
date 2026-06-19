import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { AxiosError } from 'axios';

export interface InitOnboardingRequest {
  name: string;
  site_name: string;
}

export interface InitOnboardingResponse {
  router_id: string;
  zealsync_server_endpoint: string;
  zealsync_public_key: string;
  assigned_ip: string;
  server_wg_ip: string;
}

export interface RegisterPeerRequest {
  router_id: string;
  peer_public_key: string;
}

export interface TestTunnelResponse {
  connected: boolean;
  latency_ms: number | null;
}

export interface SaveCredentialsRequest {
  router_id: string;
  username: string;
  password?: string;
  port: number;
}

export interface TestAPIResponse {
  connected: boolean;
  profiles?: string[];
  error?: string;
}

export interface ProfileItem {
  name: string;
  rate_limit: string;
}

export interface SetupProfilesRequest {
  router_id: string;
  profiles: ProfileItem[];
}

export interface SetupProfilesResponse {
  created: string[];
  failed: string[];
}

export interface CompleteOnboardingResponse {
  router_id: string;
  status: 'online';
}

export const useRouterOnboarding = () => {
  const queryClient = useQueryClient();

  const useInitOnboarding = () => {
    return useMutation<InitOnboardingResponse, AxiosError<{ detail: string }>, InitOnboardingRequest>({
      mutationFn: async (data) => {
        const response = await api.post<InitOnboardingResponse>('/admin/routers/onboarding/init', data);
        return response.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['routers'] });
      },
    });
  };

  const useRegisterPeer = () => {
    return useMutation<{ success: boolean }, AxiosError<{ detail: string }>, RegisterPeerRequest>({
      mutationFn: async (data) => {
        const response = await api.post<{ success: boolean }>('/admin/routers/onboarding/register-peer', data);
        return response.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['routers'] });
      },
    });
  };

  const useTestTunnel = () => {
    return useMutation<TestTunnelResponse, AxiosError<{ detail: string }>, { router_id: string }>({
      mutationFn: async ({ router_id }) => {
        const response = await api.post<TestTunnelResponse>('/admin/routers/onboarding/test-tunnel', { router_id });
        return response.data;
      },
    });
  };

  const useSaveCredentials = () => {
    return useMutation<{ success: boolean }, AxiosError<{ detail: string }>, SaveCredentialsRequest>({
      mutationFn: async (data) => {
        const response = await api.post<{ success: boolean }>('/admin/routers/onboarding/save-credentials', data);
        return response.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['routers'] });
      },
    });
  };

  const useTestAPI = () => {
    return useMutation<TestAPIResponse, AxiosError<{ detail: string }>, { router_id: string }>({
      mutationFn: async ({ router_id }) => {
        const response = await api.post<TestAPIResponse>('/admin/routers/onboarding/test-api', { router_id });
        return response.data;
      },
    });
  };

  const useSetupProfiles = () => {
    return useMutation<SetupProfilesResponse, AxiosError<{ detail: string }>, SetupProfilesRequest>({
      mutationFn: async (data) => {
        const response = await api.post<SetupProfilesResponse>('/admin/routers/onboarding/setup-profiles', data);
        return response.data;
      },
    });
  };

  const useCompleteOnboarding = () => {
    return useMutation<CompleteOnboardingResponse, AxiosError<{ detail: string }>, { router_id: string }>({
      mutationFn: async ({ router_id }) => {
        const response = await api.post<CompleteOnboardingResponse>('/admin/routers/onboarding/complete', { router_id });
        return response.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['routers'] });
      },
    });
  };

  return {
    useInitOnboarding,
    useRegisterPeer,
    useTestTunnel,
    useSaveCredentials,
    useTestAPI,
    useSetupProfiles,
    useCompleteOnboarding,
  };
};
