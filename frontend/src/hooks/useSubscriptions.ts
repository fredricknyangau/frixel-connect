import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Subscription, SubscriptionStatus } from '../types/subscriptions';
import { AxiosError } from 'axios';

export const useMySubscription = () => {
  return useQuery<Subscription | null, AxiosError<{ detail: string }>>({
    queryKey: ['my_subscription'],
    queryFn: async () => {
      try {
        const response = await api.get<Subscription>('/subscriptions/me');
        return response.data;
      } catch (error: any) {
        if (error.response?.status === 404) {
          return null; // Handle 404 gracefully for customers without a subscription
        }
        throw error;
      }
    },
  });
};

export const useToggleAutoRenew = () => {
  const queryClient = useQueryClient();
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
      queryClient.invalidateQueries({ queryKey: ['my_subscription'] });
    },
  });
};

export const useAdminSubscriptions = (status?: string) => {
  return useQuery<Subscription[], AxiosError<{ detail: string }>>({
    queryKey: ['admin_subscriptions', status],
    queryFn: async () => {
      const params = status && status !== 'All' ? { status: status.toLowerCase() } : {};
      const response = await api.get<Subscription[]>('/admin/subscriptions', { params });
      return response.data;
    },
  });
};

export const useSuspendSubscription = () => {
  const queryClient = useQueryClient();
  return useMutation<
    void,
    AxiosError<{ detail: string }>,
    string
  >({
    mutationFn: async (id) => {
      await api.post(`/admin/subscriptions/${id}/suspend`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin_subscriptions'] });
      queryClient.invalidateQueries({ queryKey: ['my_subscription'] }); // in case admin suspends themselves (unlikely but safe)
    },
  });
};

export const useReactivateSubscription = () => {
  const queryClient = useQueryClient();
  return useMutation<
    void,
    AxiosError<{ detail: string }>,
    string
  >({
    mutationFn: async (id) => {
      await api.post(`/admin/subscriptions/${id}/reactivate`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin_subscriptions'] });
      queryClient.invalidateQueries({ queryKey: ['my_subscription'] });
    },
  });
};
