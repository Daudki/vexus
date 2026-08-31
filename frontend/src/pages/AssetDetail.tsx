import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import Sparkline from "../components/Sparkline";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import { Field, Input, Select } from "../components/ui/Form";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../services/api";
import { Asset, AssetHistoryEntry, getAsset, getAssetHistory, updateAsset } from "../services/assets";
import { MonitoringSample, getAssetMetrics } from "../services/monitoring";
import { RiskScore, getAssetRisk, recomputeAssetRisk } from "../services/risk";

const EDITABLE_ROLES = ["admin", "security_analyst", "network_administrator"];
const CAN_RECOMPUTE_RISK_ROLES = ["admin", "security_analyst"];

const RISK_LEVEL_COLOR: Record<string, string> = {
  critical: "text-red-400",
  high: "text-orange-400",
  medium: "text-yellow-400",
  low: "text-green-400",
};

export default function AssetDetail() {
  const { assetId } = useParams<{ assetId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [asset, setAsset] = useState<Asset | null>(null);
  const [history, setHistory] = useState<AssetHistoryEntry[]>([]);
  const [latency, setLatency] = useState<MonitoringSample[]>([]);
  const [risk, setRisk] = useState<RiskScore | null>(null);
  const [riskUncomputed, setRiskUncomputed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [recomputingRisk, setRecomputingRisk] = useState(false);

  const [owner, setOwner] = useState("");
  const [deviceType, setDeviceType] = useState("");
  const [criticality, setCriticality] = useState("low");
  const [trustStatus, setTrustStatus] = useState("unknown");
  const [saving, setSaving] = useState(false);

  const canEdit = user ? EDITABLE_ROLES.includes(user.role) : false;
  const canRecomputeRisk = user ? CAN_RECOMPUTE_RISK_ROLES.includes(user.role) : false;

  async function loadRisk() {
    if (!assetId) return;
    try {
      setRisk(await getAssetRisk(assetId));
      setRiskUncomputed(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setRiskUncomputed(true);
      }
    }
  }

  async function load() {
    if (!assetId) return;
    setError(null);
    try {
      const [assetData, historyData, latencyData] = await Promise.all([
        getAsset(assetId),
        getAssetHistory(assetId),
        getAssetMetrics(assetId, "latency_ms", 30),
      ]);
      setAsset(assetData);
      setHistory(historyData);
      setLatency(latencyData);
      setOwner(assetData.owner || "");
      setDeviceType(assetData.device_type || "");
      setCriticality(assetData.criticality);
      setTrustStatus(assetData.trust_status);
      await loadRisk();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load asset.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assetId]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!assetId) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateAsset(assetId, {
        owner: owner || null,
        device_type: deviceType || null,
        criticality,
        trust_status: trustStatus,
      });
      setAsset(updated);
      setNotice("Saved.");
      const historyData = await getAssetHistory(assetId);
      setHistory(historyData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save changes.");
    } finally {
      setSaving(false);
    }
  }

  async function handleRecomputeRisk() {
    if (!assetId) return;
    setRecomputingRisk(true);
    setError(null);
    try {
      const updated = await recomputeAssetRisk(assetId);
      setRisk(updated);
      setRiskUncomputed(false);
      const assetData = await getAsset(assetId);
      setAsset(assetData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to recompute risk.");
    } finally {
      setRecomputingRisk(false);
    }
  }

  if (!asset) {
    return (
      <Layout>
        <div className="text-sm text-vexus-muted">{error || "Loading…"}</div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <button onClick={() => navigate("/assets")} className="text-xs text-vexus-muted hover:text-vexus-text mb-1">
              ← Back to assets
            </button>
            <h1 className="text-lg font-semibold tracking-tight">
              {asset.display_name || asset.hostname || asset.ip_address || asset.id}
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <Badge value={asset.status} />
              <Badge value={asset.trust_status} />
              <Badge value={asset.criticality} />
            </div>
          </div>
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-950/40 border border-red-900 rounded px-3 py-2">{error}</div>
        )}
        {notice && (
          <div className="text-sm text-blue-300 bg-blue-950/40 border border-blue-900 rounded px-3 py-2">{notice}</div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="p-4 space-y-2">
            <h2 className="text-sm font-medium text-vexus-muted">Observed details</h2>
            <dl className="text-sm space-y-1.5">
              <Row label="IP address" value={asset.ip_address} />
              <Row label="MAC address" value={asset.mac_address} />
              <Row label="Operating system" value={asset.operating_system} />
              <Row label="Vendor" value={asset.vendor} />
              <Row label="First seen" value={new Date(asset.first_seen).toLocaleString()} />
              <Row label="Last seen" value={new Date(asset.last_seen).toLocaleString()} />
            </dl>
          </Card>

          <Card className="p-4 space-y-3">
            <h2 className="text-sm font-medium text-vexus-muted">Analyst metadata</h2>
            {!canEdit && (
              <p className="text-xs text-vexus-muted">Your role can view but not edit this asset.</p>
            )}
            <form onSubmit={handleSave} className="space-y-3">
              <Field label="Owner">
                <Input value={owner} onChange={(e) => setOwner(e.target.value)} disabled={!canEdit} />
              </Field>
              <Field label="Device type">
                <Input
                  value={deviceType}
                  onChange={(e) => setDeviceType(e.target.value)}
                  disabled={!canEdit}
                  placeholder="e.g. router, workstation, IoT"
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Criticality">
                  <Select value={criticality} onChange={(e) => setCriticality(e.target.value)} disabled={!canEdit}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </Select>
                </Field>
                <Field label="Trust status">
                  <Select value={trustStatus} onChange={(e) => setTrustStatus(e.target.value)} disabled={!canEdit}>
                    <option value="unknown">Unknown</option>
                    <option value="trusted">Trusted</option>
                    <option value="untrusted">Untrusted</option>
                  </Select>
                </Field>
              </div>
              {canEdit && (
                <Button type="submit" disabled={saving}>
                  {saving ? "Saving…" : "Save changes"}
                </Button>
              )}
            </form>
          </Card>
        </div>

        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-vexus-muted">Risk</h2>
            {canRecomputeRisk && (
              <Button onClick={handleRecomputeRisk} disabled={recomputingRisk} variant="secondary">
                {recomputingRisk ? "Computing…" : "Recompute"}
              </Button>
            )}
          </div>

          {riskUncomputed && (
            <p className="text-xs text-vexus-muted">
              No risk score has been computed for this asset yet.
              {canRecomputeRisk ? " Click Recompute to generate one." : ""}
            </p>
          )}

          {risk && (
            <div className="space-y-3">
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-semibold">{risk.score.toFixed(0)}</span>
                <span className="text-vexus-muted text-sm">/ 100</span>
                <span className={`text-sm font-medium ${RISK_LEVEL_COLOR[risk.risk_level]}`}>
                  {risk.risk_level}
                </span>
              </div>
              <div className="text-xs text-vexus-muted">
                Computed {new Date(risk.computed_at).toLocaleString()}
              </div>
              <ul className="space-y-1.5 pt-2 border-t border-vexus-border">
                {risk.factors.map((factor, i) => (
                  <li key={i} className="flex items-start justify-between text-sm gap-4">
                    <div>
                      <div>{factor.label}</div>
                      <div className="text-xs text-vexus-muted">{factor.description}</div>
                    </div>
                    <span className={`text-xs font-medium shrink-0 ${factor.points < 0 ? "text-blue-400" : "text-vexus-text"}`}>
                      {factor.points > 0 ? "+" : ""}
                      {factor.points.toFixed(1)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        <Card className="p-4">
          <h2 className="text-sm font-medium text-vexus-muted mb-3">Recent latency</h2>
          <Sparkline values={latency.map((s) => s.value)} unit=" ms" />
        </Card>

        <Card className="p-4">
          <h2 className="text-sm font-medium text-vexus-muted mb-3">Change history</h2>
          {history.length === 0 && <p className="text-xs text-vexus-muted">No history recorded yet.</p>}
          <ul className="space-y-2">
            {history.map((entry) => (
              <li key={entry.id} className="text-sm border-b border-vexus-border last:border-0 pb-2">
                <div className="flex items-center justify-between">
                  <span className="text-vexus-text">{entry.change_type.replace(/_/g, " ")}</span>
                  <span className="text-xs text-vexus-muted">{new Date(entry.changed_at).toLocaleString()}</span>
                </div>
                {(entry.previous_value || entry.new_value) && (
                  <div className="text-xs text-vexus-muted mt-0.5">
                    {entry.previous_value && <span>{entry.previous_value} → </span>}
                    <span>{entry.new_value}</span>
                  </div>
                )}
                <div className="text-xs text-vexus-muted/70 mt-0.5">source: {entry.source}</div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </Layout>
  );
}

function Row({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex justify-between">
      <dt className="text-vexus-muted">{label}</dt>
      <dd>{value || <span className="text-vexus-muted">—</span>}</dd>
    </div>
  );
}
