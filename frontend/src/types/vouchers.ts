export type VoucherStatus = 'active' | 'used' | 'expired' | 'revoked' | 'pending_provision';

export interface Voucher {
  id: string;
  code: string;
  status: VoucherStatus;
  expires_at: string;
  activated_at: string | null;
  created_at: string;
  customer_id: string;
  package_id: string;
  package_name: string;
  payment_id: string;
}
