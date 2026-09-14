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
