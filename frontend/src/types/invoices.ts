export interface Invoice {
  id: string;
  payment_id: string;
  invoice_number: number;
  kra_etims_qr_code: string | null;
  pdf_url: string | null;
  amount_kes: number;
  created_at: string;
}
