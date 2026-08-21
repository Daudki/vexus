import { apiRequest } from "./api";

export interface MonitoringSample {
  id: string;
  metric_type: "availability" | "latency_ms" | "packet_loss_pct";
  value: number;
  timestamp: string;
  is_synthetic: boolean;
}

export interface NetworkHealthOverview {
  online: number;
  offline: number;
  unknown: number;
  average_latency_ms: number | null;
  data_quality_warnings: string[];
}

export function getOverview(): Promise<NetworkHealthOverview> {
  return apiRequest<NetworkHealthOverview>("/monitoring/overview");
}

export function getAssetMetrics(assetId: string, metricType?: string, limit = 50): Promise<MonitoringSample[]> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (metricType) query.set("metric_type", metricType);
  return apiRequest<MonitoringSample[]>(`/monitoring/assets/${assetId}/metrics?${query.toString()}`);
}

export function triggerPoll(): Promise<{ assets_checked: number; went_offline: number; went_online: number; missing_flagged: number }> {
  return apiRequest("/monitoring/poll", { method: "POST" });
}
