import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Invoice } from '../types/invoices';
import { AxiosError } from 'axios';

export const useAdminInvoices = () => {
  return useQuery<Invoice[], AxiosError<{ detail: string }>>({
    queryKey: ['admin_invoices'],
    queryFn: async () => {
      const response = await api.get<Invoice[]>('/admin/invoices');
      return response.data;
    },
  });
};

export const useMyInvoices = () => {
  return useQuery<Invoice[], AxiosError<{ detail: string }>>({
    queryKey: ['my_invoices'],
    queryFn: async () => {
      const response = await api.get<Invoice[]>('/invoices/me');
      return response.data;
    },
  });
};
