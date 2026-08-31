import { apiRequest } from "./api";

export interface Asset {
  id: string;
  ip_address: string | null;
  mac_address: string | null;
  hostname: string | null;
  device_type: string | null;
  operating_system: string | null;
  vendor: string | null;
  status: "online" | "offline" | "unknown";
  criticality: "low" | "medium" | "high" | "critical";
  trust_status: "trusted" | "unknown" | "untrusted";
  owner: string | null;
  first_seen: string;
  last_seen: string;
  risk_score: number;
  display_name: string;
}

export interface AssetHistoryEntry {
  id: string;
  change_type: string;
  previous_value: string;
  new_value: string;
  source: string;
  changed_at: string;
}

export interface AssetListParams {
  search?: string;
  status?: string;
  trust_status?: string;
  criticality?: string;
  sort_by?: string;
  sort_desc?: boolean;
  limit?: number;
  offset?: number;
}

export interface AssetUpdate {
  device_type?: string | null;
  owner?: string | null;
  criticality?: string | null;
  trust_status?: string | null;
}

export function listAssets(params: AssetListParams = {}): Promise<Asset[]> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  const qs = query.toString();
  return apiRequest<Asset[]>(`/assets${qs ? `?${qs}` : ""}`);
}

export function getAsset(assetId: string): Promise<Asset> {
  return apiRequest<Asset>(`/assets/${assetId}`);
}

export function getAssetHistory(assetId: string): Promise<AssetHistoryEntry[]> {
  return apiRequest<AssetHistoryEntry[]>(`/assets/${assetId}/history`);
}

export function updateAsset(assetId: string, payload: AssetUpdate): Promise<Asset> {
  return apiRequest<Asset>(`/assets/${assetId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
