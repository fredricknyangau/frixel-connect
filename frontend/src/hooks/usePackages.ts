import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { queryKeys } from '../lib/queryKeys';
import { useAuthContext } from '../context/AuthContext';
import { Package, PackageCreateRequest } from '../types/packages';

export function usePackages() {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery({
    queryKey: queryKeys.packages.all(tenantId),
    queryFn: async () => {
      const response = await api.get<Package[]>('/packages');
      return response.data;
    },
    enabled: !!tenantId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCreatePackage() {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation({
    mutationFn: async (data: PackageCreateRequest) => {
      const response = await api.post<Package>('/packages', data);
      return response.data;
    },
    onSuccess: () => {
      if (tenantId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.packages.all(tenantId) });
      }
    },
  });
}

export function useUpdatePackage() {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: PackageCreateRequest }) => {
      const response = await api.put<Package>(`/packages/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      if (tenantId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.packages.all(tenantId) });
      }
    },
  });
}

export function useDeactivatePackage() {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation({
    mutationFn: async (id: string) => {
      const response = await api.delete(`/packages/${id}`);
      return response.data;
    },
    onSuccess: () => {
      if (tenantId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.packages.all(tenantId) });
      }
    },
  });
}
