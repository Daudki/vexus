import { apiRequest } from "./api";

export interface Incident {
  id: string;
  title: string;
  description: string;
  severity: "informational" | "low" | "medium" | "high" | "critical";
  confidence: number;
  status: "open" | "investigating" | "resolved" | "false_positive" | "closed";
  assigned_to: string | null;
  resolution: string;
  created_at: string;
  updated_at: string;
}

export interface IncidentDetail extends Incident {
  alert_ids: string[];
  asset_ids: string[];
}

export interface TimelineEntry {
  timestamp: string;
  kind: "event" | "note" | "audit";
  summary: string;
  detail: string;
}

export interface Note {
  id: string;
  author_username: string;
  content: string;
  created_at: string;
}

export function listIncidents(statusFilter?: string): Promise<Incident[]> {
  const qs = statusFilter ? `?status_filter=${statusFilter}` : "";
  return apiRequest<Incident[]>(`/incidents${qs}`);
}

export function getIncident(incidentId: string): Promise<IncidentDetail> {
  return apiRequest<IncidentDetail>(`/incidents/${incidentId}`);
}

export function createIncident(payload: {
  title: string;
  description?: string;
  alert_ids?: string[];
  asset_ids?: string[];
}): Promise<IncidentDetail> {
  return apiRequest<IncidentDetail>("/incidents", { method: "POST", body: JSON.stringify(payload) });
}

export function updateIncident(
  incidentId: string,
  payload: { status?: string; assigned_to?: string; resolution?: string; title?: string; description?: string }
): Promise<IncidentDetail> {
  return apiRequest<IncidentDetail>(`/incidents/${incidentId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function getTimeline(incidentId: string): Promise<TimelineEntry[]> {
  return apiRequest<TimelineEntry[]>(`/incidents/${incidentId}/timeline`);
}

export function listNotes(incidentId: string): Promise<Note[]> {
  return apiRequest<Note[]>(`/incidents/${incidentId}/notes`);
}

export function addNote(incidentId: string, content: string): Promise<Note> {
  return apiRequest<Note>(`/incidents/${incidentId}/notes`, { method: "POST", body: JSON.stringify({ content }) });
}

export function linkAsset(incidentId: string, assetId: string): Promise<IncidentDetail> {
  return apiRequest<IncidentDetail>(`/incidents/${incidentId}/assets`, {
    method: "POST",
    body: JSON.stringify({ asset_id: assetId }),
  });
}
