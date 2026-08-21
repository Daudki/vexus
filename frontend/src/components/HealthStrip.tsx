import { useEffect, useState } from "react";
import { apiRequest } from "../services/api";

interface PlatformStatus {
  database: string;
  workers: Record<string, string>;
  ai_provider: string;
  checked_at: string;
}

const DOT: Record<string, string> = {
  ok: "🟢",
  configured: "🟢",
  degraded: "🟡",
  not_configured: "🟡",
  stopped: "🔴",
  unavailable: "🔴",
};

function label(name: string, status: string): string {
  const readable = name.replace(/_/g, " ");
  const dot = DOT[status] ?? "⚪";
  return `${dot} ${readable}`;
}

/**
 * VEXUS Health — this is deliberately the first thing rendered on the
 * dashboard. A security platform that has silently stopped collecting
 * data is more dangerous than one that's honest about being degraded.
 */
export default function HealthStrip() {
  const [status, setStatus] = useState<PlatformStatus | null>(null);

  useEffect(() => {
    apiRequest<PlatformStatus>("/health/status").then(setStatus).catch(() => setStatus(null));
  }, []);

  if (!status) return null;

  const items = [
    label("database", status.database),
    ...Object.entries(status.workers).map(([name, s]) => label(name, s)),
    label("ai provider", status.ai_provider),
  ];

  return (
    <div className="flex flex-wrap gap-4 text-xs text-vexus-muted bg-vexus-panel border border-vexus-border rounded-lg px-4 py-2">
      {items.map((item) => (
        <span key={item}>{item}</span>
      ))}
    </div>
  );
}
