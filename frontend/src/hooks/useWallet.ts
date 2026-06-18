import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { WalletBalance } from '../types/wallet';
import { Voucher } from '../types/vouchers';
import { AxiosError } from 'axios';

export const useWalletBalance = () => {
  return useQuery<WalletBalance, AxiosError<{ detail: string }>>({
    queryKey: ['wallet_balance'],
    queryFn: async () => {
      const response = await api.get<{ balance: number; paybill_number: string; wallet_reference: string }>('/reseller/wallet');
      return {
        balance_kes: response.data.balance,
        paybill_number: response.data.paybill_number,
        wallet_reference: response.data.wallet_reference,
      };
    },
  });
};

export const useGenerateWalletVoucher = () => {
  const queryClient = useQueryClient();
  return useMutation<
    Voucher,
    AxiosError<{ detail: string }>,
    { customer_id: string; package_id: string }
  >({
    mutationFn: async (data) => {
      const response = await api.post<Voucher>('/reseller/vouchers/generate', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wallet_balance'] });
      queryClient.invalidateQueries({ queryKey: ['vouchers'] });
      queryClient.invalidateQueries({ queryKey: ['reseller_vouchers'] }); // for reseller vouchers lists
    },
  });
};
export const useWalletTransactions = () => {
  return useQuery<any, AxiosError<{ detail: string }>>({
    queryKey: ['wallet_transactions'],
    queryFn: async () => {
      const response = await api.get<{ transactions: any[] }>('/reseller/wallet');
      return response.data.transactions;
    },
  });
};
