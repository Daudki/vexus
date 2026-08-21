import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import { Field, Input } from "../components/ui/Form";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../services/api";
import { ScanJob, listScans, startScan } from "../services/discovery";

const CAN_SCAN_ROLES = ["admin", "network_administrator"];

export default function Discovery() {
  const { user } = useAuth();
  const [scans, setScans] = useState<ScanJob[] | null>(null);
  const [targetRanges, setTargetRanges] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const canScan = user ? CAN_SCAN_ROLES.includes(user.role) : false;

  async function load() {
    try {
      setScans(await listScans());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load scan history.");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const ranges = targetRanges
      .split(",")
      .map((r) => r.trim())
      .filter(Boolean);

    try {
      await startScan(ranges);
      setTargetRanges("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Scan failed to start.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Discovery</h1>
          <p className="text-xs text-vexus-muted mt-1 max-w-2xl">
            Scans are refused outright for any target outside the ranges an administrator has
            explicitly authorized (<code className="text-vexus-text">AUTHORIZED_SCAN_RANGES</code>{" "}
            in the backend environment). Only scan networks you own or are authorized to assess.
          </p>
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-950/40 border border-red-900 rounded px-3 py-2">{error}</div>
        )}

        {canScan ? (
          <Card className="p-4">
            <form onSubmit={handleSubmit} className="flex items-end gap-3">
              <div className="flex-1">
                <Field label="Target ranges (comma-separated CIDR, e.g. 10.0.0.0/24, 192.168.1.0/24)">
                  <Input
                    value={targetRanges}
                    onChange={(e) => setTargetRanges(e.target.value)}
                    placeholder="10.0.0.0/24"
                    required
                  />
                </Field>
              </div>
              <Button type="submit" disabled={submitting}>
                {submitting ? "Scanning…" : "Start scan"}
              </Button>
            </form>
          </Card>
        ) : (
          <Card className="p-4">
            <p className="text-xs text-vexus-muted">
              Your role ({user?.role.replace("_", " ")}) can view scan history but not start new scans.
              Only Network Administrator and Admin roles can trigger discovery.
            </p>
          </Card>
        )}

        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="text-xs text-vexus-muted border-b border-vexus-border">
              <tr>
                <th className="text-left px-4 py-2">Targets</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-left px-4 py-2">Hosts</th>
                <th className="text-left px-4 py-2">New</th>
                <th className="text-left px-4 py-2">Changed</th>
                <th className="text-left px-4 py-2">Started</th>
              </tr>
            </thead>
            <tbody>
              {scans === null && (
                <tr>
                  <td colSpan={6} className="text-center text-vexus-muted text-xs py-6">
                    Loading…
                  </td>
                </tr>
              )}
              {scans?.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-center text-vexus-muted text-xs py-6">
                    No scans yet.
                  </td>
                </tr>
              )}
              {scans?.map((scan) => (
                <tr key={scan.id} className="border-b border-vexus-border last:border-0">
                  <td className="px-4 py-2 text-vexus-muted">{scan.target_ranges.join(", ")}</td>
                  <td className="px-4 py-2">
                    <Badge value={scan.status} />
                  </td>
                  <td className="px-4 py-2">{scan.hosts_discovered}</td>
                  <td className="px-4 py-2">{scan.new_assets}</td>
                  <td className="px-4 py-2">{scan.changed_assets}</td>
                  <td className="px-4 py-2 text-xs text-vexus-muted">
                    {new Date(scan.started_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        {scans?.some((s) => s.status === "failed" || s.status === "refused") && (
          <Card className="p-4">
            <h2 className="text-sm font-medium text-vexus-muted mb-2">Errors from failed/refused scans</h2>
            <ul className="space-y-1 text-xs">
              {scans
                .filter((s) => s.error_message)
                .map((s) => (
                  <li key={s.id} className="text-red-400">
                    {s.target_ranges.join(", ")}: {s.error_message}
                  </li>
                ))}
            </ul>
          </Card>
        )}
      </div>
    </Layout>
  );
}
