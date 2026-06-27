import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { queryKeys } from '../lib/queryKeys';
import { useAuthContext } from '../context/AuthContext';
import { WalletBalance } from '../types/wallet';
import { Voucher } from '../types/vouchers';
import { AxiosError } from 'axios';

export const useWalletBalance = () => {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';
  const resellerId = user?.user_id ?? '';

  return useQuery<WalletBalance, AxiosError<{ detail: string }>>({
    queryKey: queryKeys.wallets.balance(tenantId, resellerId),
    queryFn: async () => {
      const response = await api.get<{ balance: number; paybill_number: string; wallet_reference: string }>(
        '/reseller/wallet'
      );
      return {
        balance_kes: response.data.balance,
        paybill_number: response.data.paybill_number,
        wallet_reference: response.data.wallet_reference,
      };
    },
    enabled: !!tenantId && !!resellerId,
  });
};

export const useGenerateWalletVoucher = () => {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';
  const resellerId = user?.user_id ?? '';

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
      if (!tenantId) return;
      queryClient.invalidateQueries({ queryKey: queryKeys.wallets.balance(tenantId, resellerId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.vouchers.reseller(tenantId) });
    },
  });
};

interface WalletTransaction {
  id: string;
  amount_kes: number;
  transaction_type: string;
  created_at: string;
}

export const useWalletTransactions = () => {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';
  const resellerId = user?.user_id ?? '';

  return useQuery<WalletTransaction[], AxiosError<{ detail: string }>>({
    queryKey: queryKeys.wallets.transactions(tenantId, resellerId),
    queryFn: async () => {
      const response = await api.get<{ transactions: WalletTransaction[] }>('/reseller/wallet');
      return response.data.transactions;
    },
    enabled: !!tenantId && !!resellerId,
  });
};
