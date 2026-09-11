import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import HealthStrip from "../components/HealthStrip";
import NetworkHealthPanel from "../components/NetworkHealthPanel";
import TopRisksPanel from "../components/TopRisksPanel";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import { Asset, listAssets } from "../services/assets";
import { Alert, listAlerts } from "../services/detection";
import { Incident, listIncidents } from "../services/incidents";
import { ScanJob, listScans } from "../services/discovery";
import { AIStatus, getAIStatus } from "../services/ai";

const TILES = [
  { to: "/assets", title: "Asset inventory", description: "Search, filter, and edit observed devices." },
  { to: "/alerts", title: "Alert operations", description: "Review detections and tune rules." },
  { to: "/incidents", title: "Investigations", description: "Follow linked evidence and timelines." },
  { to: "/discovery", title: "Authorized discovery", description: "Run a scan and see what changed." },
  { to: "/topology", title: "Network topology", description: "Explore observed asset relationships." },
];

function displayAsset(assetId: string | null, assets: Asset[]): string {
  if (!assetId) return "Unassigned asset";
  const asset = assets.find((item) => item.id === assetId);
  return asset?.display_name || asset?.ip_address || assetId;
}

function formatTime(value: string): string {
  return new Date(value).toLocaleString([], { dateStyle: "short", timeStyle: "short" });
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [scans, setScans] = useState<ScanJob[]>([]);
  const [aiStatus, setAIStatus] = useState<AIStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadOverview() {
    setLoading(true);
    setError(null);
    try {
      const [assetData, alertData, incidentData, scanData, aiData] = await Promise.all([
        listAssets({ limit: 200, sort_by: "last_seen", sort_desc: true }),
        listAlerts(),
        listIncidents(),
        listScans(),
        getAIStatus(),
      ]);
      setAssets(assetData);
      setAlerts(alertData);
      setIncidents(incidentData);
      setScans(scanData);
      setAIStatus(aiData);
    } catch {
      setError("Some operational data could not be loaded. Try refreshing.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadOverview();
  }, []);

  const activeAlerts = alerts.filter((alert) => !["resolved", "closed", "false_positive"].includes(alert.status));
  const openIncidents = incidents.filter((incident) => ["open", "investigating"].includes(incident.status));
  const onlineAssets = assets.filter((asset) => asset.status === "online");
  const unknownAssets = assets.filter((asset) => asset.trust_status === "unknown");
  const latestScan = scans[0];
  const attentionAlerts = activeAlerts.slice(0, 5);
  const attentionIncidents = openIncidents.slice(0, 3);

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-vexus-accent">Operations overview</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-white">What is happening now</h1>
            <p className="mt-1 text-sm text-vexus-muted">A live view of devices, detections, investigations, and collection health.</p>
          </div>
          <button type="button" onClick={loadOverview} disabled={loading} className="rounded border border-vexus-border px-3 py-2 text-xs text-vexus-text transition-colors hover:border-vexus-accent disabled:opacity-50">
            {loading ? "Refreshing..." : "Refresh overview"}
          </button>
        </div>

        <HealthStrip />
        {error && <div className="rounded border border-yellow-900 bg-yellow-950/40 px-3 py-2 text-sm text-yellow-300">{error}</div>}

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
          {[
            ["Devices", assets.length, "/assets", "text-white"],
            ["Online", onlineAssets.length, "/assets?status=online", "text-green-400"],
            ["Unknown trust", unknownAssets.length, "/assets?trust_status=unknown", "text-yellow-400"],
            ["Active alerts", activeAlerts.length, "/alerts", "text-red-400"],
            ["Open incidents", openIncidents.length, "/incidents", "text-orange-400"],
            ["Last scan", latestScan ? latestScan.hosts_discovered : "-", "/discovery", "text-vexus-accent"],
          ].map(([label, value, to, color]) => (
            <button key={String(label)} type="button" onClick={() => navigate(String(to))} className="rounded-lg border border-vexus-border bg-vexus-panel p-4 text-left transition-colors hover:border-vexus-accent">
              <div className={`text-2xl font-semibold ${color}`}>{value}</div>
              <div className="mt-1 text-xs text-vexus-muted">{label}</div>
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-vexus-border px-4 py-3">
              <div><h2 className="text-sm font-medium text-white">Needs attention</h2><p className="mt-1 text-xs text-vexus-muted">Active alerts and investigations requiring a decision.</p></div>
              <button type="button" onClick={() => navigate("/alerts")} className="text-xs text-vexus-accent hover:underline">View alerts</button>
            </div>
            <div className="divide-y divide-vexus-border">
              {attentionAlerts.map((alert) => (
                <button key={alert.id} type="button" onClick={() => navigate("/alerts")} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-vexus-border/20">
                  <Badge value={alert.severity} /><span className="min-w-0 flex-1 truncate text-sm text-vexus-text">{alert.description || alert.rule_key}</span><span className="shrink-0 text-[11px] text-vexus-muted">{displayAsset(alert.asset_id, assets)}</span>
                </button>
              ))}
              {attentionIncidents.map((incident) => (
                <button key={incident.id} type="button" onClick={() => navigate(`/incidents/${incident.id}`)} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-vexus-border/20">
                  <Badge value={incident.severity} /><span className="min-w-0 flex-1 truncate text-sm text-vexus-text">{incident.title}</span><span className="shrink-0 text-[11px] text-vexus-muted">Incident</span>
                </button>
              ))}
              {!attentionAlerts.length && !attentionIncidents.length && <p className="px-4 py-8 text-center text-xs text-vexus-muted">No active alerts or open investigations.</p>}
            </div>
          </Card>

          <Card className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-vexus-border px-4 py-3">
              <div><h2 className="text-sm font-medium text-white">Recent discovery</h2><p className="mt-1 text-xs text-vexus-muted">The latest evidence entering the asset inventory.</p></div>
              <button type="button" onClick={() => navigate("/discovery")} className="text-xs text-vexus-accent hover:underline">Open discovery</button>
            </div>
            <div className="divide-y divide-vexus-border">
              {scans.slice(0, 4).map((scan) => (
                <button key={scan.id} type="button" onClick={() => navigate("/discovery")} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-vexus-border/20">
                  <span className={`h-2 w-2 rounded-full ${scan.status === "completed" ? "bg-green-400" : scan.status === "failed" ? "bg-red-400" : "bg-yellow-400"}`} />
                  <span className="min-w-0 flex-1 truncate text-sm">{scan.target_ranges.join(", ")}</span><span className="shrink-0 text-right text-[11px] text-vexus-muted">{scan.hosts_discovered} hosts<br />{formatTime(scan.started_at)}</span>
                </button>
              ))}
              {!scans.length && <p className="px-4 py-8 text-center text-xs text-vexus-muted">No discovery runs yet.</p>}
            </div>
          </Card>
        </div>

        <Card className="border-vexus-accent/30 bg-vexus-accent/5 p-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2"><span className={`h-2 w-2 rounded-full ${aiStatus?.configured ? "bg-green-400" : "bg-yellow-400"}`} /><h2 className="text-sm font-medium text-white">AI investigation assistant</h2></div>
              <p className="mt-1 text-xs text-vexus-muted">
                {aiStatus?.configured
                  ? `${aiStatus.provider} is ready. Explain alerts from Alert Operations or summarize an incident from its detail view.`
                  : "Not active in this deployment. Configure a provider key on the backend to enable grounded explanations and incident summaries."}
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              <button type="button" onClick={() => navigate("/alerts")} className="rounded border border-vexus-border px-3 py-2 text-xs text-vexus-text hover:border-vexus-accent">Explain an alert</button>
              <button type="button" onClick={() => navigate("/incidents")} className="rounded border border-vexus-border px-3 py-2 text-xs text-vexus-text hover:border-vexus-accent">Summarize an incident</button>
            </div>
          </div>
        </Card>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2"><NetworkHealthPanel /><TopRisksPanel /></div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
          {TILES.map((tile) => (
            <Card key={tile.to} className="cursor-pointer p-4 transition-colors hover:border-vexus-accent" onClick={() => navigate(tile.to)}>
              <h2 className="text-sm font-medium">{tile.title}</h2><p className="mt-1 text-xs text-vexus-muted">{tile.description}</p>
            </Card>
          ))}
        </div>
      </div>
    </Layout>
  );
}
