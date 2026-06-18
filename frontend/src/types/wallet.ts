export type WalletTxnType = 'topup' | 'debit' | 'adjustment';

export interface WalletTransaction {
  id: string;
  type: WalletTxnType;
  amount_kes: number;
  balance_after: number;
  reference: string;
  created_at: string;
}

export interface WalletBalance {
  balance_kes: number;
  paybill_number: string;
  wallet_reference: string;
}
