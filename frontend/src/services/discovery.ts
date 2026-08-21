import { apiRequest } from "./api";

export interface ScanJob {
  id: string;
  target_ranges: string[];
  status: "running" | "completed" | "failed" | "refused";
  started_at: string;
  completed_at: string | null;
  hosts_discovered: number;
  new_assets: number;
  changed_assets: number;
  error_message: string;
}

export function listScans(): Promise<ScanJob[]> {
  return apiRequest<ScanJob[]>("/discovery/scans");
}

export function startScan(targetRanges: string[]): Promise<ScanJob> {
  return apiRequest<ScanJob>("/discovery/scans", {
    method: "POST",
    body: JSON.stringify({ target_ranges: targetRanges }),
  });
}
