import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { queryKeys } from '../lib/queryKeys';
import { useAuthContext } from '../context/AuthContext';
import { MikrotikRouter, RouterCreateRequest } from '../types/routers';
import { AxiosError } from 'axios';

export const useRouters = () => {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery<MikrotikRouter[], AxiosError<{ detail: string }>>({
    queryKey: queryKeys.routers.all(tenantId),
    queryFn: async () => {
      const response = await api.get<MikrotikRouter[]>('/admin/routers');
      return response.data;
    },
    enabled: !!tenantId,
  });
};

export const useCreateRouter = () => {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation<MikrotikRouter, AxiosError<{ detail: string }>, RouterCreateRequest>({
    mutationFn: async (data) => {
      const response = await api.post<MikrotikRouter>('/admin/routers', data);
      return response.data;
    },
    onSuccess: () => {
      if (tenantId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.routers.all(tenantId) });
      }
    },
  });
};

export const useUpdateRouter = () => {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation<
    MikrotikRouter,
    AxiosError<{ detail: string }>,
    { id: string; data: Partial<RouterCreateRequest> }
  >({
    mutationFn: async ({ id, data }) => {
      const response = await api.put<MikrotikRouter>(`/admin/routers/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      if (tenantId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.routers.all(tenantId) });
      }
    },
  });
};

export const useDeleteRouter = () => {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation<void, AxiosError<{ detail: string }>, string>({
    mutationFn: async (id) => {
      await api.delete(`/admin/routers/${id}`);
    },
    onSuccess: () => {
      if (tenantId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.routers.all(tenantId) });
      }
    },
  });
};
