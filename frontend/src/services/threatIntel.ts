import { apiRequest } from "./api";

export interface Vulnerability {
  id: string;
  cve_id: string;
  source: string;
  description: string;
  cvss_score: number | null;
  cvss_severity: string | null;
  cvss_version: string | null;
  published_at: string | null;
  last_modified_at: string | null;
  cwe_ids: string[];
  affected_cpes: string[];
  references: string[];
  is_rejected: boolean;
}

export interface VulnerabilityListResponse {
  items: Vulnerability[];
  total: number;
}

export interface ThreatIntelStatus {
  provider: string;
  configured: boolean;
}

export interface SyncCVEResponse {
  cve_id: string;
  created: boolean;
  updated: boolean;
  event_id: string | null;
  source: string;
}

export function getThreatIntelStatus(): Promise<ThreatIntelStatus> {
  return apiRequest<ThreatIntelStatus>("/threat-intel/status");
}

export function listVulnerabilities(
  params: { search?: string; severity?: string; limit?: number; offset?: number } = {}
): Promise<VulnerabilityListResponse> {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  if (params.severity) query.set("severity", params.severity);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  const qs = query.toString();
  return apiRequest<VulnerabilityListResponse>(`/threat-intel/vulnerabilities${qs ? `?${qs}` : ""}`);
}

export function syncCVE(cveId: string): Promise<SyncCVEResponse> {
  return apiRequest<SyncCVEResponse>(`/threat-intel/sync/cve/${encodeURIComponent(cveId)}`, { method: "POST" });
}

export interface AssetVulnerabilityLink {
  id: string;
  asset_id: string;
  cve_id: string;
  cvss_score: number | null;
  cvss_severity: string | null;
  is_rejected: boolean;
  confidence: "confirmed" | "inferred";
  match_source: string;
  created_at: string;
}

export interface MatchSummary {
  assets_evaluated: number;
  links_created: number;
  links_removed: number;
}

export function listAssetVulnerabilities(assetId: string): Promise<AssetVulnerabilityLink[]> {
  return apiRequest<AssetVulnerabilityLink[]>(`/threat-intel/assets/${assetId}/vulnerabilities`);
}

export function linkAssetVulnerability(assetId: string, cveId: string): Promise<AssetVulnerabilityLink> {
  return apiRequest<AssetVulnerabilityLink>(`/threat-intel/assets/${assetId}/vulnerabilities`, {
    method: "POST",
    body: JSON.stringify({ cve_id: cveId }),
  });
}

export function unlinkAssetVulnerability(assetId: string, cveId: string): Promise<void> {
  return apiRequest<void>(`/threat-intel/assets/${assetId}/vulnerabilities/${encodeURIComponent(cveId)}`, {
    method: "DELETE",
  });
}

export function runVulnerabilityMatching(): Promise<MatchSummary> {
  return apiRequest<MatchSummary>("/threat-intel/match", { method: "POST" });
}
