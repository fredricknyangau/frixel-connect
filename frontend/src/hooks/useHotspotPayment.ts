import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';

interface PortalSTKPushRequest {
  phone: string;
  package_id: string;
  tenant_id: string;
  mac_address?: string;
  client_ip?: string;
}

interface PaymentResponse {
  id: string;
  customer_id: string;
  package_id: string;
  amount_kes: number;
  status: string;
  phone_number: string;
  created_at: string;
}

interface PaymentStatusResponse {
  payment_id: string;
  status: string;
  voucher_code?: string;
}

export function useHotspotSTKPush() {
  return useMutation<PaymentResponse, Error, PortalSTKPushRequest>({
    mutationFn: async (data) => {
      // Unauthenticated endpoint
      const response = await api.post<PaymentResponse>('/hotspot/payments/stk', data);
      return response.data;
    },
  });
}

export function useHotspotPaymentStatus(paymentId: string | null, enabled: boolean) {
  return useQuery<PaymentStatusResponse, Error>({
    queryKey: ['hotspot-payment-status', paymentId],
    queryFn: async () => {
      if (!paymentId) throw new Error("No payment ID");
      const response = await api.get<PaymentStatusResponse>(`/hotspot/payments/${paymentId}/status`);
      return response.data;
    },
    enabled: enabled && !!paymentId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      // Stop polling if confirmed or failed
      if (status === 'confirmed' || status === 'failed') {
        return false;
      }
      return 3000; // poll every 3 seconds
    },
  });
}
