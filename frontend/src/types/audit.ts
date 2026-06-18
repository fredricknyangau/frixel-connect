export interface AuditLogEntry {
  id: string;
  actor_user_id: string;
  actor_email: string;
  action: string;
  target_type: string;
  target_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
}
