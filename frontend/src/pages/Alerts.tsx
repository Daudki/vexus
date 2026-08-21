import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AIPanel from "../components/AIPanel";
import Layout from "../components/Layout";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import { Select } from "../components/ui/Form";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../services/api";
import { explainAlert } from "../services/ai";
import {
  Alert,
  DetectionRuleConfig,
  listAlerts,
  listDetectionRules,
  triggerDetectionRun,
  updateAlert,
  updateDetectionRule,
} from "../services/detection";
import { createIncident } from "../services/incidents";

const CAN_MANAGE_ROLES = ["admin", "security_analyst", "network_administrator"];
const CAN_RUN_DETECTION_ROLES = ["admin", "security_analyst"];
const CAN_EDIT_RULES_ROLES = ["admin", "security_analyst"];

const STATUS_OPTIONS = ["new", "acknowledged", "investigating", "resolved", "false_positive", "closed"];

export default function Alerts() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [rules, setRules] = useState<DetectionRuleConfig[] | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [showRules, setShowRules] = useState(false);
  const [openingIncidentFor, setOpeningIncidentFor] = useState<string | null>(null);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);

  const canManage = user ? CAN_MANAGE_ROLES.includes(user.role) : false;
  const canRunDetection = user ? CAN_RUN_DETECTION_ROLES.includes(user.role) : false;
  const canEditRules = user ? CAN_EDIT_RULES_ROLES.includes(user.role) : false;

  async function loadAlerts() {
    try {
      setAlerts(await listAlerts({ status_filter: statusFilter || undefined }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load alerts.");
    }
  }

  async function loadRules() {
    try {
      setRules(await listDetectionRules());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load detection rules.");
    }
  }

  useEffect(() => {
    loadAlerts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  async function handleRunDetection() {
    setError(null);
    setNotice(null);
    setRunning(true);
    try {
      const summary = await triggerDetectionRun();
      setNotice(
        `Detection run: ${summary.events_evaluated} events evaluated, ${summary.findings_produced} findings, ` +
          `${summary.alerts_created} alerts created, ${summary.alerts_updated} updated.`
      );
      await loadAlerts();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Detection run failed.");
    } finally {
      setRunning(false);
    }
  }

  async function handleStatusChange(alertId: string, status: string) {
    setError(null);
    try {
      await updateAlert(alertId, { status });
      await loadAlerts();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update alert.");
    }
  }

  async function handleToggleRule(rule: DetectionRuleConfig) {
    setError(null);
    try {
      await updateDetectionRule(rule.rule_key, { enabled: !rule.enabled });
      await loadRules();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update rule.");
    }
  }

  async function handleShowRules() {
    setShowRules(!showRules);
    if (!rules) await loadRules();
  }

  async function handleOpenIncident(alert: Alert) {
    setError(null);
    setOpeningIncidentFor(alert.id);
    try {
      const incident = await createIncident({
        title: `${alert.rule_key.replace(/_/g, " ")} — investigation`,
        description: alert.description,
        alert_ids: [alert.id],
      });
      navigate(`/incidents/${incident.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to open incident.");
    } finally {
      setOpeningIncidentFor(null);
    }
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Alerts</h1>
            <p className="text-xs text-vexus-muted mt-1 max-w-2xl">
              Alerts are deduplicated: repeated detections of the same issue on the same asset merge
              into one alert (see occurrence count) instead of flooding the queue.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={handleShowRules} className="text-xs text-vexus-muted hover:text-vexus-text border border-vexus-border rounded px-2.5 py-1.5">
              {showRules ? "Hide" : "Show"} detection rules
            </button>
            {canRunDetection && (
              <Button onClick={handleRunDetection} disabled={running}>
                {running ? "Running…" : "Run detection"}
              </Button>
            )}
          </div>
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-950/40 border border-red-900 rounded px-3 py-2">{error}</div>
        )}
        {notice && (
          <div className="text-sm text-blue-300 bg-blue-950/40 border border-blue-900 rounded px-3 py-2">{notice}</div>
        )}

        {showRules && (
          <Card className="p-4 space-y-2">
            <h2 className="text-sm font-medium text-vexus-muted">Detection rules</h2>
            {rules === null && <p className="text-xs text-vexus-muted">Loading…</p>}
            {rules?.map((rule) => (
              <div key={rule.rule_key} className="flex items-center justify-between border-b border-vexus-border last:border-0 py-2">
                <div>
                  <div className="text-sm">{rule.display_name}</div>
                  <div className="text-xs text-vexus-muted">
                    confidence ≥ {rule.confidence_threshold} · alert after {rule.alert_threshold} occurrence(s) ·
                    suppress repeats for {rule.suppression_window_minutes}m
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge value={rule.enabled ? "online" : "offline"} />
                  {canEditRules && (
                    <button
                      onClick={() => handleToggleRule(rule)}
                      className="text-xs text-vexus-muted hover:text-vexus-text border border-vexus-border rounded px-2 py-1"
                    >
                      {rule.enabled ? "Disable" : "Enable"}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </Card>
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
                <th className="text-left px-4 py-2">Rule</th>
                <th className="text-left px-4 py-2">Severity</th>
                <th className="text-left px-4 py-2">Confidence</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-left px-4 py-2">Occurrences</th>
                <th className="text-left px-4 py-2">Last seen</th>
                {canManage && <th className="px-4 py-2"></th>}
              </tr>
            </thead>
            <tbody>
              {alerts === null && (
                <tr>
                  <td colSpan={7} className="text-center text-vexus-muted text-xs py-6">
                    Loading…
                  </td>
                </tr>
              )}
              {alerts?.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center text-vexus-muted text-xs py-6">
                    No alerts. Run detection to evaluate recent events, or adjust the status filter.
                  </td>
                </tr>
              )}
              {alerts?.map((alert) => (
                <tr key={alert.id} className="border-b border-vexus-border last:border-0">
                  <td className="px-4 py-2">
                    <div>{alert.rule_key.replace(/_/g, " ")}</div>
                    <div className="text-xs text-vexus-muted">{alert.description}</div>
                  </td>
                  <td className="px-4 py-2">
                    <Badge value={alert.severity} />
                  </td>
                  <td className="px-4 py-2 text-vexus-muted text-xs">{(alert.confidence * 100).toFixed(0)}%</td>
                  <td className="px-4 py-2">
                    <Badge value={alert.status} />
                    {alert.suppressed && <span className="text-xs text-vexus-muted ml-1">(suppressed)</span>}
                  </td>
                  <td className="px-4 py-2 text-vexus-muted">{alert.occurrence_count}</td>
                  <td className="px-4 py-2 text-xs text-vexus-muted">{new Date(alert.last_seen).toLocaleString()}</td>
                  {canManage && (
                    <td className="px-4 py-2">
                      <Select
                        value={alert.status}
                        onChange={(e) => handleStatusChange(alert.id, e.target.value)}
                        className="text-xs"
                      >
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s} value={s}>
                            {s.replace(/_/g, " ")}
                          </option>
                        ))}
                      </Select>
                    </td>
                  )}
                  {canManage && (
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2 whitespace-nowrap">
                        <button
                          onClick={() => setSelectedAlertId(alert.id)}
                          className="text-xs text-vexus-muted hover:text-vexus-text"
                        >
                          Explain
                        </button>
                        <button
                          onClick={() => handleOpenIncident(alert)}
                          disabled={openingIncidentFor === alert.id}
                          className="text-xs text-vexus-accent hover:underline disabled:opacity-50"
                        >
                          {openingIncidentFor === alert.id ? "Opening…" : "Open incident"}
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        {selectedAlertId && (
          <AIPanel
            targetType="alert"
            targetId={selectedAlertId}
            canRequest={canManage}
            requestLabel="Explain alert"
            onRequest={() => explainAlert(selectedAlertId)}
          />
        )}
      </div>
    </Layout>
  );
}
