import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Session } from '../types/sessions';

export function useAdminSessions() {
  return useQuery({
    queryKey: ['adminSessions'],
    queryFn: async () => {
      const response = await api.get<Session[]>('/admin/sessions');
      return response.data;
    },
  });
}

export function useCustomerSessions() {
  return useQuery({
    queryKey: ['customerSessions'],
    queryFn: async () => {
      const response = await api.get<Session[]>('/sessions/me');
      return response.data;
    },
  });
}
