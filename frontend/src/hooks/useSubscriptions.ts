import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { queryKeys } from '../lib/queryKeys';
import { useAuthContext } from '../context/AuthContext';
import { Subscription } from '../types/subscriptions';
import { AxiosError } from 'axios';

export const useMySubscription = () => {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery<Subscription | null, AxiosError<{ detail: string }>>({
    queryKey: queryKeys.subscriptions.mine(tenantId),
    queryFn: async () => {
      try {
        const response = await api.get<Subscription>('/subscriptions/me');
        return response.data;
      } catch (error: unknown) {
        if (axiosIs404(error)) {
          return null;
        }
        throw error;
      }
    },
    enabled: !!tenantId,
  });
};

function axiosIs404(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    (error as { response?: { status?: number } }).response?.status === 404
  );
}

export const useToggleAutoRenew = () => {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation<
    Subscription,
    AxiosError<{ detail: string }>,
    { auto_renew: boolean }
  >({
    mutationFn: async (data) => {
      const response = await api.put<Subscription>('/subscriptions/me', data);
      return response.data;
    },
    onSuccess: () => {
      if (tenantId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.subscriptions.mine(tenantId) });
      }
    },
  });
};

export const useAdminSubscriptions = (status?: string) => {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery<Subscription[], AxiosError<{ detail: string }>>({
    queryKey: queryKeys.subscriptions.admin(tenantId, status),
    queryFn: async () => {
      const params = status && status !== 'All' ? { status: status.toLowerCase() } : {};
      const response = await api.get<Subscription[]>('/admin/subscriptions', { params });
      return response.data;
    },
    enabled: !!tenantId,
  });
};

export const useSuspendSubscription = () => {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation<void, AxiosError<{ detail: string }>, string>({
    mutationFn: async (id) => {
      await api.post(`/admin/subscriptions/${id}/suspend`);
    },
    onSuccess: () => {
      if (!tenantId) return;
      queryClient.invalidateQueries({ queryKey: ['subscriptions', 'admin', tenantId] });
      queryClient.invalidateQueries({ queryKey: queryKeys.subscriptions.mine(tenantId) });
    },
  });
};

export const useReactivateSubscription = () => {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation<void, AxiosError<{ detail: string }>, string>({
    mutationFn: async (id) => {
      await api.post(`/admin/subscriptions/${id}/reactivate`);
    },
    onSuccess: () => {
      if (!tenantId) return;
      queryClient.invalidateQueries({ queryKey: ['subscriptions', 'admin', tenantId] });
      queryClient.invalidateQueries({ queryKey: queryKeys.subscriptions.mine(tenantId) });
    },
  });
};
