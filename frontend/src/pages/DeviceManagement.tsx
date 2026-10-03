import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import { Field, Input, Select } from "../components/ui/Form";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../services/api";
import { Asset, listAssets } from "../services/assets";
import {
  DEVICE_ACTION_META,
  DeviceActionType,
  DeviceTask,
  DeviceTaskCreate,
  EnrollmentIssued,
  ManagedDevice,
  listDeviceTasks,
  listDevices,
  enrollDevice,
  queueDeviceTask,
  revokeDevice,
} from "../services/deviceManagement";

const ADMIN_ONLY = ["admin"];

export default function DeviceManagement() {
  const { user } = useAuth();
  const isAdmin = user ? ADMIN_ONLY.includes(user.role) : false;

  const [devices, setDevices] = useState<ManagedDevice[] | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Enroll form state
  const [enrollAssetId, setEnrollAssetId] = useState("");
  const [enrolling, setEnrolling] = useState(false);
  const [issued, setIssued] = useState<EnrollmentIssued | null>(null);

  // Per-device task panel state (one at a time — modal-ish but inline)
  const [openTaskDeviceId, setOpenTaskDeviceId] = useState<string | null>(null);
  const [tasks, setTasks] = useState<DeviceTask[] | null>(null);
  const [taskAction, setTaskAction] = useState<DeviceActionType>("status_check");
  const [taskParams, setTaskParams] = useState("{}");
  const [taskConfirm, setTaskConfirm] = useState(false);
  const [queueing, setQueueing] = useState(false);

  async function loadDevices() {
    try {
      setDevices(await listDevices());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load managed devices.");
    }
  }

  async function loadAssetsForEnroll() {
    try {
      const listed = await listAssets({ limit: 200 });
      setAssets(listed);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load assets for enrollment.");
    }
  }

  useEffect(() => {
    loadDevices();
    if (isAdmin) loadAssetsForEnroll();
  }, [isAdmin]);

  function resetEnrollForm() {
    setEnrollAssetId("");
    setIssued(null);
  }

  async function handleEnroll(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setIssued(null);
    setEnrolling(true);
    try {
      const result = await enrollDevice(enrollAssetId);
      setIssued(result);
      await loadDevices();
      setNotice(
        `Enrollment token issued for asset. Token expires at ${new Date(
          result.expires_at,
        ).toLocaleString()}. Copy it now — it will not be shown again.`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Enrollment failed.");
    } finally {
      setEnrolling(false);
    }
  }

  async function handleRevoke(device: ManagedDevice) {
    if (!confirm(`Revoke agent credential for this device? The agent will stop authenticating on its next request. This cannot be undone.`)) {
      return;
    }
    setError(null);
    setNotice(null);
    try {
      await revokeDevice(device.id);
      await loadDevices();
      setNotice("Device revoked. Agent credential is no longer valid.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Revoke failed.");
    }
  }

  async function openTaskPanel(device: ManagedDevice) {
    setOpenTaskDeviceId(device.id);
    setTasks(null);
    setError(null);
    setNotice(null);
    try {
      setTasks(await listDeviceTasks(device.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load tasks.");
    }
  }

  function closeTaskPanel() {
    setOpenTaskDeviceId(null);
    setTasks(null);
    setTaskAction("status_check");
    setTaskParams("{}");
    setTaskConfirm(false);
  }

  async function handleQueueTask(e: React.FormEvent) {
    e.preventDefault();
    if (!openTaskDeviceId) return;

    const meta = DEVICE_ACTION_META.find((m) => m.value === taskAction)!;
    if (meta.requiresConfirm && !taskConfirm) {
      setError(`'${meta.label}' is irreversible and requires explicit confirmation. Check the confirm box.`);
      return;
    }

    let params: Record<string, unknown> = {};
    try {
      params = taskParams.trim() ? JSON.parse(taskParams) : {};
    } catch {
      setError("Params must be valid JSON (or '{}' for no params).");
      return;
    }

    setError(null);
    setNotice(null);
    setQueueing(true);
    const payload: DeviceTaskCreate = {
      action_type: taskAction,
      params,
      confirm: taskConfirm,
    };
    try {
      await queueDeviceTask(openTaskDeviceId, payload);
      setTasks(await listDeviceTasks(openTaskDeviceId));
      setTaskParams("{}");
      setTaskConfirm(false);
      setNotice(`Task '${meta.label}' queued. The agent will pick it up on its next poll.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to queue task.");
    } finally {
      setQueueing(false);
    }
  }

  const selectedMeta = DEVICE_ACTION_META.find((m) => m.value === taskAction);

  return (
    <Layout>
      <div className="space-y-6">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Device Management</h1>
          <p className="text-xs text-vexus-muted mt-1 max-w-2xl">
            Authorized device administration. Enrolling a device issues a single-use enrollment
            token (15-minute TTL) that an agent redeems for a durable agent credential. Every
            queued task passes through the policy engine before it&apos;s created — destructive
            actions (<code className="text-vexus-text">reboot</code>,{" "}
            <code className="text-vexus-text">isolate</code>) require Admin role AND explicit
            confirmation.
          </p>
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-950/40 border border-red-900 rounded px-3 py-2">{error}</div>
        )}
        {notice && (
          <div className="text-sm text-emerald-400 bg-emerald-950/30 border border-emerald-900 rounded px-3 py-2">{notice}</div>
        )}

        {issued && (
          <Card className="p-4 border-amber-700/60">
            <h2 className="text-sm font-medium text-amber-300 mb-2">
              Enrollment token — copy now, shown only once
            </h2>
            <div className="bg-vexus-bg border border-vexus-border rounded p-2 font-mono text-xs break-all text-amber-200">
              {issued.enrollment_token}
            </div>
            <p className="text-[11px] text-vexus-muted mt-2">
              Device ID: <code>{issued.device.id}</code> · Status:{" "}
              <code>{issued.device.status}</code> · Expires at{" "}
              {new Date(issued.expires_at).toLocaleString()}
            </p>
            <div className="mt-3 flex gap-2">
              <Button
                type="button"
                onClick={() => {
                  navigator.clipboard?.writeText(issued.enrollment_token).catch(() => {});
                  setNotice("Enrollment token copied to clipboard.");
                }}
              >
                Copy token
              </Button>
              <Button type="button" variant="ghost" onClick={resetEnrollForm}>
                Done
              </Button>
            </div>
          </Card>
        )}

        {isAdmin && (
          <Card className="p-4">
            <h2 className="text-sm font-medium mb-2">Enroll a new managed device</h2>
            <form onSubmit={handleEnroll} className="flex items-end gap-3">
              <div className="flex-1">
                <Field label="Asset to enroll">
                  <Select
                    value={enrollAssetId}
                    onChange={(e) => setEnrollAssetId(e.target.value)}
                    required
                  >
                    <option value="">Select an asset…</option>
                    {assets.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.display_name} {a.ip_address ? `(${a.ip_address})` : ""}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
              <Button type="submit" disabled={enrolling || !enrollAssetId}>
                {enrolling ? "Issuing…" : "Issue enrollment token"}
              </Button>
            </form>
            {assets.length === 0 && (
              <p className="text-[11px] text-vexus-muted mt-2">
                No assets found. Run a discovery scan first to populate the asset inventory.
              </p>
            )}
          </Card>
        )}

        {!isAdmin && (
          <Card className="p-4">
            <p className="text-xs text-vexus-muted">
              Your role ({user?.role.replace("_", " ")}) can view managed devices but not enroll
              or revoke. Only Admin role can perform those actions.
            </p>
          </Card>
        )}

        <Card className="overflow-hidden">
          <div className="px-4 py-3 border-b border-vexus-border">
            <h2 className="text-sm font-medium">Managed devices</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="text-xs text-vexus-muted border-b border-vexus-border">
              <tr>
                <th className="text-left px-4 py-2">Asset</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-left px-4 py-2">Agent</th>
                <th className="text-left px-4 py-2">Reported OS</th>
                <th className="text-left px-4 py-2">Last check-in</th>
                <th className="text-left px-4 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {devices === null && (
                <tr>
                  <td colSpan={6} className="text-center text-vexus-muted text-xs py-6">
                    Loading…
                  </td>
                </tr>
              )}
              {devices?.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-center text-vexus-muted text-xs py-6">
                    No managed devices. Enroll one above.
                  </td>
                </tr>
              )}
              {devices?.map((d) => {
                const asset = assets.find((a) => a.id === d.asset_id);
                const label = asset?.display_name ?? d.asset_id;
                return (
                  <tr key={d.id} className="border-b border-vexus-border last:border-0">
                    <td className="px-4 py-2">
                      <div className="text-vexus-text">{label}</div>
                      <div className="text-[11px] text-vexus-muted">
                        id {d.id.slice(0, 8)}…
                      </div>
                    </td>
                    <td className="px-4 py-2">
                      <Badge value={d.status} />
                    </td>
                    <td className="px-4 py-2 text-vexus-muted">
                      {d.agent_version ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-vexus-muted">
                      {d.reported_os ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-xs text-vexus-muted">
                      {d.last_checkin_at
                        ? new Date(d.last_checkin_at).toLocaleString()
                        : "never"}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() =>
                            openTaskDeviceId === d.id
                              ? closeTaskPanel()
                              : openTaskPanel(d)
                          }
                        >
                          {openTaskDeviceId === d.id ? "Close" : "Tasks"}
                        </Button>
                        {isAdmin && d.status !== "revoked" && (
                          <Button
                            type="button"
                            variant="ghost"
                            onClick={() => handleRevoke(d)}
                          >
                            Revoke
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>

        {openTaskDeviceId && (
          <Card className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium">
                Task queue for device{" "}
                <code className="text-vexus-muted">{openTaskDeviceId.slice(0, 8)}…</code>
              </h2>
              <Button type="button" variant="ghost" onClick={closeTaskPanel}>
                Close
              </Button>
            </div>

            <form onSubmit={handleQueueTask} className="space-y-3">
              <div className="flex items-end gap-3">
                <div className="w-60">
                  <Field label="Action">
                    <Select
                      value={taskAction}
                      onChange={(e) => {
                        const next = e.target.value as DeviceActionType;
                        setTaskAction(next);
                        // Reset confirm when switching away from a destructive action
                        const meta = DEVICE_ACTION_META.find((m) => m.value === next);
                        if (!meta?.requiresConfirm) setTaskConfirm(false);
                      }}
                    >
                      {DEVICE_ACTION_META.map((m) => (
                        <option key={m.value} value={m.value}>
                          {m.label}
                          {m.requiresConfirm ? " (requires confirm)" : ""}
                        </option>
                      ))}
                    </Select>
                  </Field>
                </div>
                <div className="flex-1">
                  <Field label="Params (JSON object, e.g. {} or {&quot;service&quot;:&quot;sshd&quot;})">
                    <Input
                      value={taskParams}
                      onChange={(e) => setTaskParams(e.target.value)}
                    />
                  </Field>
                </div>
                {selectedMeta?.requiresConfirm && (
                  <Field label="">
                    <label className="inline-flex items-center gap-2 text-xs text-vexus-text">
                      <input
                        type="checkbox"
                        checked={taskConfirm}
                        onChange={(e) => setTaskConfirm(e.target.checked)}
                        className="h-3.5 w-3.5"
                      />
                      Confirm destructive
                    </label>
                  </Field>
                )}
                <Button type="submit" disabled={queueing}>
                  {queueing ? "Queuing…" : "Queue task"}
                </Button>
              </div>
              {selectedMeta && (
                <p className="text-[11px] text-vexus-muted/80">
                  {selectedMeta.description}
                </p>
              )}
            </form>

            <div className="mt-4">
              <h3 className="text-xs text-vexus-muted mb-2">Recent tasks</h3>
              {tasks === null ? (
                <p className="text-xs text-vexus-muted">Loading…</p>
              ) : tasks.length === 0 ? (
                <p className="text-xs text-vexus-muted">No tasks queued for this device.</p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="text-vexus-muted border-b border-vexus-border">
                    <tr>
                      <th className="text-left px-2 py-1.5">Action</th>
                      <th className="text-left px-2 py-1.5">Status</th>
                      <th className="text-left px-2 py-1.5">Result</th>
                      <th className="text-left px-2 py-1.5">Queued</th>
                      <th className="text-left px-2 py-1.5">Completed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tasks.map((t) => (
                      <tr key={t.id} className="border-b border-vexus-border last:border-0">
                        <td className="px-2 py-1.5">
                          <code className="text-vexus-text/80">{t.action_type}</code>
                        </td>
                        <td className="px-2 py-1.5">
                          <Badge value={t.status} />
                        </td>
                        <td className="px-2 py-1.5 text-vexus-muted max-w-md truncate">
                          {t.result || t.error_message || "—"}
                        </td>
                        <td className="px-2 py-1.5 text-vexus-muted">
                          {new Date(t.created_at).toLocaleString()}
                        </td>
                        <td className="px-2 py-1.5 text-vexus-muted">
                          {t.completed_at
                            ? new Date(t.completed_at).toLocaleString()
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </Card>
        )}
      </div>
    </Layout>
  );
}
