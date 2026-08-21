import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import Badge from "../components/ui/Badge";
import Card from "../components/ui/Card";
import { Select } from "../components/ui/Form";
import { ApiError } from "../services/api";
import { Incident, listIncidents } from "../services/incidents";

const STATUS_OPTIONS = ["open", "investigating", "resolved", "false_positive", "closed"];

export default function Incidents() {
  const navigate = useNavigate();
  const [incidents, setIncidents] = useState<Incident[] | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      setIncidents(await listIncidents(statusFilter || undefined));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load incidents.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  return (
    <Layout>
      <div className="space-y-6">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Incidents</h1>
          <p className="text-xs text-vexus-muted mt-1 max-w-2xl">
            Every incident here was created by an analyst linking evidence (alerts and/or assets) —
            VEXUS doesn't auto-generate incidents yet, since that needs Correlate (not built).
          </p>
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-950/40 border border-red-900 rounded px-3 py-2">{error}</div>
        )}

        <Card className="p-4 flex items-center gap-3">
          <span className="text-xs text-vexus-muted">Filter by status</span>
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="max-w-xs">
            <option value="">All</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, " ")}
              </option>
            ))}
          </Select>
        </Card>

        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="text-xs text-vexus-muted border-b border-vexus-border">
              <tr>
                <th className="text-left px-4 py-2">Title</th>
                <th className="text-left px-4 py-2">Severity</th>
                <th className="text-left px-4 py-2">Confidence</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-left px-4 py-2">Updated</th>
              </tr>
            </thead>
            <tbody>
              {incidents === null && (
                <tr>
                  <td colSpan={5} className="text-center text-vexus-muted text-xs py-6">
                    Loading…
                  </td>
                </tr>
              )}
              {incidents?.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center text-vexus-muted text-xs py-6">
                    No incidents yet. Open an alert from the Alerts page to start one.
                  </td>
                </tr>
              )}
              {incidents?.map((incident) => (
                <tr
                  key={incident.id}
                  onClick={() => navigate(`/incidents/${incident.id}`)}
                  className="border-b border-vexus-border last:border-0 cursor-pointer hover:bg-vexus-border/20"
                >
                  <td className="px-4 py-2">{incident.title}</td>
                  <td className="px-4 py-2">
                    <Badge value={incident.severity} />
                  </td>
                  <td className="px-4 py-2 text-vexus-muted text-xs">{(incident.confidence * 100).toFixed(0)}%</td>
                  <td className="px-4 py-2">
                    <Badge value={incident.status} />
                  </td>
                  <td className="px-4 py-2 text-xs text-vexus-muted">{new Date(incident.updated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </Layout>
  );
}
