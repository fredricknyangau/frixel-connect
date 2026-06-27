import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { queryKeys } from '../lib/queryKeys';
import { useAuthContext } from '../context/AuthContext';
import {
  User,
  CustomerCreateRequest,
  UserUpdateRequest,
  AdminUserCreateRequest,
  AdminUserUpdateRequest,
} from '../types/users';

export function useAdminCustomers() {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery({
    queryKey: queryKeys.users.adminCustomers(tenantId),
    queryFn: async () => {
      const response = await api.get<User[]>('/admin/users');
      return response.data;
    },
    enabled: !!tenantId,
  });
}

export function useResellerCustomers() {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery({
    queryKey: queryKeys.users.resellerCustomers(tenantId),
    queryFn: async () => {
      const response = await api.get<User[]>('/reseller/customers');
      return response.data;
    },
    enabled: !!tenantId,
  });
}

export function useCustomerProfile() {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery({
    queryKey: queryKeys.users.profile(tenantId),
    queryFn: async () => {
      const response = await api.get<User>('/customers/me');
      return response.data;
    },
    enabled: !!tenantId,
  });
}

export function useCreateResellerCustomer() {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation({
    mutationFn: async (data: CustomerCreateRequest) => {
      const response = await api.post<User>('/reseller/customers', data);
      return response.data;
    },
    onSuccess: () => {
      if (tenantId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.users.resellerCustomers(tenantId) });
      }
    },
  });
}

export function useUpdateCustomerProfile() {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation({
    mutationFn: async (data: UserUpdateRequest) => {
      const response = await api.put<User>('/customers/me', data);
      return response.data;
    },
    onSuccess: () => {
      if (tenantId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.users.profile(tenantId) });
      }
    },
  });
}

export function useAdminCreateUser() {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation({
    mutationFn: async (data: AdminUserCreateRequest) => {
      const response = await api.post<User>('/admin/users', data);
      return response.data;
    },
    onSuccess: () => {
      if (tenantId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.users.adminCustomers(tenantId) });
      }
    },
  });
}

export function useAdminUpdateUser() {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: AdminUserUpdateRequest }) => {
      const response = await api.put<User>(`/admin/users/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      if (tenantId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.users.adminCustomers(tenantId) });
      }
    },
  });
}

export function useAdminDeleteUser() {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation({
    mutationFn: async (id: string) => {
      const response = await api.delete(`/admin/users/${id}`);
      return response.data;
    },
    onSuccess: () => {
      if (tenantId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.users.adminCustomers(tenantId) });
      }
    },
  });
}
