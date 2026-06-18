import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { MikrotikRouter, RouterCreateRequest } from '../types/routers';
import { AxiosError } from 'axios';

export const useRouters = () => {
  return useQuery<MikrotikRouter[], AxiosError<{ detail: string }>>({
    queryKey: ['routers'],
    queryFn: async () => {
      const response = await api.get<MikrotikRouter[]>('/admin/routers');
      return response.data;
    },
  });
};

export const useCreateRouter = () => {
  const queryClient = useQueryClient();
  return useMutation<MikrotikRouter, AxiosError<{ detail: string }>, RouterCreateRequest>({
    mutationFn: async (data) => {
      const response = await api.post<MikrotikRouter>('/admin/routers', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['routers'] });
    },
  });
};

export const useUpdateRouter = () => {
  const queryClient = useQueryClient();
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
      queryClient.invalidateQueries({ queryKey: ['routers'] });
    },
  });
};

export const useDeleteRouter = () => {
  const queryClient = useQueryClient();
  return useMutation<void, AxiosError<{ detail: string }>, string>({
    mutationFn: async (id) => {
      await api.delete(`/admin/routers/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['routers'] });
    },
  });
};
