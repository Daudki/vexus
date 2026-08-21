import { apiRequest } from "./api";

export interface Alert {
  id: string;
  rule_key: string;
  asset_id: string | null;
  severity: "informational" | "low" | "medium" | "high" | "critical";
  confidence: number;
  status: "new" | "acknowledged" | "investigating" | "resolved" | "false_positive" | "closed";
  description: string;
  evidence: string[];
  dedup_key: string;
  occurrence_count: number;
  first_seen: string;
  last_seen: string;
  suppressed: boolean;
  assigned_to: string | null;
}

export interface DetectionRuleConfig {
  id: string;
  rule_key: string;
  display_name: string;
  description: string;
  enabled: boolean;
  severity: string;
  confidence_threshold: number;
  alert_threshold: number;
  suppression_window_minutes: number;
}

export interface DetectionRunSummary {
  events_evaluated: number;
  findings_produced: number;
  alerts_created: number;
  alerts_updated: number;
}

export interface DetectionRuleCatalog {
  implemented: string[];
  not_implemented: string[];
}

export function listAlerts(params: { status_filter?: string; severity?: string } = {}): Promise<Alert[]> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) query.set(key, value);
  });
  const qs = query.toString();
  return apiRequest<Alert[]>(`/alerts${qs ? `?${qs}` : ""}`);
}

export function updateAlert(alertId: string, payload: { status?: string; assigned_to?: string }): Promise<Alert> {
  return apiRequest<Alert>(`/alerts/${alertId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function triggerDetectionRun(): Promise<DetectionRunSummary> {
  return apiRequest<DetectionRunSummary>("/detection/run", { method: "POST" });
}

export function listDetectionRules(): Promise<DetectionRuleConfig[]> {
  return apiRequest<DetectionRuleConfig[]>("/detection/rules");
}

export function getDetectionCatalog(): Promise<DetectionRuleCatalog> {
  return apiRequest<DetectionRuleCatalog>("/detection/rules/catalog");
}

export function updateDetectionRule(ruleKey: string, payload: Partial<DetectionRuleConfig>): Promise<DetectionRuleConfig> {
  return apiRequest<DetectionRuleConfig>(`/detection/rules/${ruleKey}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
