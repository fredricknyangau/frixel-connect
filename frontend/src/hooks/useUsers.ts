import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { User, CustomerCreateRequest, UserUpdateRequest, AdminUserCreateRequest, AdminUserUpdateRequest } from '../types/users';

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

export function useCreateResellerCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: CustomerCreateRequest) => {
      const response = await api.post<User>('/reseller/customers', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resellerCustomers'] });
    },
  });
}

export function useUpdateCustomerProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: UserUpdateRequest) => {
      const response = await api.put<User>('/customers/me', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customerProfile'] });
    },
  });
}

export function useAdminCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: AdminUserCreateRequest) => {
      const response = await api.post<User>('/admin/users', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminCustomers'] });
    },
  });
}

export function useAdminUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: AdminUserUpdateRequest }) => {
      const response = await api.put<User>(`/admin/users/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminCustomers'] });
    },
  });
}

export function useAdminDeleteUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const response = await api.delete(`/admin/users/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminCustomers'] });
    },
  });
}
