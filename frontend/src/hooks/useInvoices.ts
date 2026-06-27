import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { queryKeys } from '../lib/queryKeys';
import { useAuthContext } from '../context/AuthContext';
import { Invoice } from '../types/invoices';
import { AxiosError } from 'axios';

export const useAdminInvoices = () => {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery<Invoice[], AxiosError<{ detail: string }>>({
    queryKey: queryKeys.invoices.admin(tenantId),
    queryFn: async () => {
      const response = await api.get<Invoice[]>('/admin/invoices');
      return response.data;
    },
    enabled: !!tenantId,
  });
};

export const useMyInvoices = () => {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery<Invoice[], AxiosError<{ detail: string }>>({
    queryKey: queryKeys.invoices.mine(tenantId),
    queryFn: async () => {
      const response = await api.get<Invoice[]>('/invoices/me');
      return response.data;
    },
    enabled: !!tenantId,
  });
};
