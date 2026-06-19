export type PaymentStatus = 'pending' | 'confirmed' | 'failed' | 'cancelled';

export interface Payment {
  id: string;
  customer_id: string;
  package_id: string;
  package_name: string;
  amount_kes: number;
  status: PaymentStatus;
  phone_number: string;
  mpesa_receipt_number: string | null;
  created_at: string;
}

export interface STKPushRequest {
  phone: string;
  package_id: string;
}

export interface STKPushResponse {
  payment_id: string;
}

export interface PaymentStatusResponse {
  payment_id: string;
  status: PaymentStatus;
  voucher_code: string | null;
}
