export interface Session {
  id: string;
  voucher_id: string;
  customer_id: string;
  mac_address: string | null;
  ip_address: string | null;
  bytes_uploaded: number;
  bytes_downloaded: number;
  started_at: string;
  ended_at: string | null;
}
