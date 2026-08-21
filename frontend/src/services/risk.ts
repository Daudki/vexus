import { apiRequest } from "./api";

export interface RiskFactor {
  factor_key: string;
  label: string;
  points: number;
  description: string;
}

export interface RiskScore {
  id: string;
  asset_id: string;
  score: number;
  risk_level: "low" | "medium" | "high" | "critical";
  computed_at: string;
  factors: RiskFactor[];
}

export interface RiskScoreHistoryEntry {
  id: string;
  score: number;
  risk_level: string;
  computed_at: string;
}

export interface RecomputeSummary {
  assets_scored: number;
  average_score: number;
  detection_data_stale: boolean;
}

export interface TopRiskAsset {
  id: string;
  hostname: string | null;
  ip_address: string | null;
  risk_score: number;
  criticality: string;
  trust_status: string;
}

export function getAssetRisk(assetId: string): Promise<RiskScore> {
  return apiRequest<RiskScore>(`/risk/assets/${assetId}`);
}

export function getAssetRiskHistory(assetId: string): Promise<RiskScoreHistoryEntry[]> {
  return apiRequest<RiskScoreHistoryEntry[]>(`/risk/assets/${assetId}/history`);
}

export function recomputeAssetRisk(assetId: string): Promise<RiskScore> {
  return apiRequest<RiskScore>(`/risk/assets/${assetId}/recompute`, { method: "POST" });
}

export function recomputeAllRisk(): Promise<RecomputeSummary> {
  return apiRequest<RecomputeSummary>("/risk/recompute", { method: "POST" });
}

export function getTopRiskAssets(limit = 5): Promise<TopRiskAsset[]> {
  return apiRequest<TopRiskAsset[]>(`/risk/top?limit=${limit}`);
}
