import { apiRequest } from "./api";

export type ScanProfile =
  | "host_discovery"
  | "stealth_syn"
  | "service_version"
  | "os_detect"
  | "full";

/** Human-readable label + short description for each profile, shown in
 * the dropdown so operators pick the right one without having to
 * remember the exact nmap flag semantics. */
export const SCAN_PROFILE_OPTIONS: {
  value: ScanProfile;
  label: string;
  hint: string;
}[] = [
  {
    value: "stealth_syn",
    label: "Stealth SYN scan (default)",
    hint: "TCP SYN half-open scan. Detects open ports without completing the connection in the target's socket table.",
  },
  {
    value: "host_discovery",
    label: "Host discovery (ping scan only)",
    hint: "Just host liveness — no port scan. Cheapest, but no open ports reported.",
  },
  {
    value: "service_version",
    label: "Service + version detection",
    hint: "Stealth SYN + per-port banner grabbing. Slower but exposes service fingerprints for change detection.",
  },
  {
    value: "os_detect",
    label: "OS detection",
    hint: "Stealth SYN + TCP/IP stack fingerprinting. Requires root on most hosts; nmap will skip silently if unavailable.",
  },
  {
    value: "full",
    label: "Full (service + OS)",
    hint: "Stealth SYN + version + OS. Slowest and noisiest; use during a maintenance window.",
  },
];

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
  profile: ScanProfile;
}

export function listScans(): Promise<ScanJob[]> {
  return apiRequest<ScanJob[]>("/discovery/scans");
}

export function startScan(
  targetRanges: string[],
  profile?: ScanProfile,
): Promise<ScanJob> {
  const body: Record<string, unknown> = { target_ranges: targetRanges };
  if (profile) {
    body.profile = profile;
  }
  return apiRequest<ScanJob>("/discovery/scans", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
