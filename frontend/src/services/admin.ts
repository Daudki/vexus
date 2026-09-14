import { apiRequest } from "./api";

export interface ScanRangesSettings {
  ranges: string[];
}

export interface SystemStats {
  total_users: number;
  active_users: number;
  total_assets: number;
  active_assets: number;
  total_alerts: number;
  new_alerts: number;
  total_incidents: number;
  open_incidents: number;
  health_status: string;
}

export function getScanRanges(): Promise<ScanRangesSettings> {
  return apiRequest<ScanRangesSettings>("/admin/settings/scan-ranges");
}

export function updateScanRanges(ranges: string[]): Promise<ScanRangesSettings> {
  return apiRequest<ScanRangesSettings>("/admin/settings/scan-ranges", {
    method: "PUT",
    body: JSON.stringify({ ranges }),
  });
}

export function getSystemStats(): Promise<SystemStats> {
  return apiRequest<SystemStats>("/admin/stats");
}
