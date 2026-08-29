import { apiRequest } from "./api";

export interface ScanRangesSettings {
  ranges: string[];
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
