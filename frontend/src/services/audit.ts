import { apiRequest } from "./api";

export interface AuditLogEntry {
  id: string;
  actor_user_id: string | null;
  actor_username: string;
  action: string;
  target_type: string;
  target_id: string;
  detail: string;
  ip_address: string;
  success: boolean;
  created_at: string;
}

export interface AuditLogFilters {
  action?: string;
  target_type?: string;
  target_id?: string;
  actor_username?: string;
  limit?: number;
  offset?: number;
}

export function listAuditLogs(filters: AuditLogFilters = {}): Promise<AuditLogEntry[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value));
  });
  const qs = params.toString();
  return apiRequest<AuditLogEntry[]>(`/audit-logs${qs ? `?${qs}` : ""}`);
}
