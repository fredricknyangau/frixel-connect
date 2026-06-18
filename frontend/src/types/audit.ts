export interface AuditLogEntry {
  id: string;
  actor_user_id: string;
  actor_email?: string;
  actor?: {
    id: string;
    email: string;
  };
  action: string;
  target_type: string;
  target_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}
