import { useEffect, useState } from "react";
import { apiRequest } from "../services/api";

interface NetworkHealthOverview {
  online: number;
  offline: number;
  unknown: number;
  average_latency_ms: number | null;
  data_quality_warnings: string[];
}

export default function NetworkHealthPanel() {
  const [overview, setOverview] = useState<NetworkHealthOverview | null>(null);

  useEffect(() => {
    apiRequest<NetworkHealthOverview>("/monitoring/overview").then(setOverview).catch(() => setOverview(null));
  }, []);

  if (!overview) return null;

  return (
    <div className="bg-vexus-panel border border-vexus-border rounded-lg p-4 space-y-3">
      <h2 className="text-sm font-medium text-vexus-muted">Network Health</h2>

      <div className="grid grid-cols-3 gap-4 text-center">
        <div>
          <div className="text-2xl font-semibold text-green-400">{overview.online}</div>
          <div className="text-xs text-vexus-muted">Online</div>
        </div>
        <div>
          <div className="text-2xl font-semibold text-red-400">{overview.offline}</div>
          <div className="text-xs text-vexus-muted">Offline</div>
        </div>
        <div>
          <div className="text-2xl font-semibold text-vexus-muted">{overview.unknown}</div>
          <div className="text-xs text-vexus-muted">Unknown</div>
        </div>
      </div>

      {overview.average_latency_ms !== null && (
        <div className="text-xs text-vexus-muted text-center">
          Avg. latency (recent samples): {overview.average_latency_ms.toFixed(1)} ms
        </div>
      )}

      {overview.data_quality_warnings.map((warning) => (
        <div
          key={warning}
          className="text-xs text-yellow-400 bg-yellow-950/40 border border-yellow-900 rounded px-3 py-2"
        >
          ⚠ {warning}
        </div>
      ))}
    </div>
  );
}
