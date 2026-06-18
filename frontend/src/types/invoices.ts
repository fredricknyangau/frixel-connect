export interface Invoice {
  id: string;
  payment_id: string;
  invoice_number: string;
  kra_etims_qr_code: string;
  pdf_url: string;
  amount_kes: number;
  created_at: string;
}
