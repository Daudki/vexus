import { apiRequest } from "./api";

export interface AIQueryLog {
  id: string;
  query_type: string;
  target_type: string;
  target_id: string;
  question: string;
  observed_facts: string[];
  inferences: string[];
  hypotheses: string[];
  recommendations: string[];
  confidence: number;
  provider: string;
  created_at: string;
}

export interface AIStatus {
  provider: string;
  configured: boolean;
}

export function getAIStatus(): Promise<AIStatus> {
  return apiRequest<AIStatus>("/ai/status");
}

export function explainAlert(alertId: string): Promise<AIQueryLog> {
  return apiRequest<AIQueryLog>(`/ai/alerts/${alertId}/explain`, { method: "POST" });
}

export function summarizeIncident(incidentId: string): Promise<AIQueryLog> {
  return apiRequest<AIQueryLog>(`/ai/incidents/${incidentId}/summarize`, { method: "POST" });
}

export function askAI(contextType: string, contextId: string, question: string): Promise<AIQueryLog> {
  return apiRequest<AIQueryLog>("/ai/ask", {
    method: "POST",
    body: JSON.stringify({ context_type: contextType, context_id: contextId, question }),
  });
}

export function listAIQueries(targetType: string, targetId: string): Promise<AIQueryLog[]> {
  return apiRequest<AIQueryLog[]>(`/ai/queries?target_type=${targetType}&target_id=${targetId}`);
}
