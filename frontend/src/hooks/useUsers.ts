import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { User } from '../types/users';

export function useAdminCustomers() {
  return useQuery({
    queryKey: ['adminCustomers'],
    queryFn: async () => {
      const response = await api.get<User[]>('/admin/users');
      return response.data;
    },
  });
}

export function useResellerCustomers() {
  return useQuery({
    queryKey: ['resellerCustomers'],
    queryFn: async () => {
      const response = await api.get<User[]>('/reseller/customers');
      return response.data;
    },
  });
}

export function useCustomerProfile() {
  return useQuery({
    queryKey: ['customerProfile'],
    queryFn: async () => {
      const response = await api.get<User>('/customers/me');
      return response.data;
    },
  });
}
