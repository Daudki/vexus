import { Fragment, useEffect, useState } from "react";
import Layout from "../components/Layout";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../services/api";
import {
  getThreatIntelStatus,
  listVulnerabilities,
  syncCVE,
  ThreatIntelStatus,
  Vulnerability,
} from "../services/threatIntel";

const PAGE_SIZE = 25;

// Sync makes a real outbound call to NVD and is restricted server-side
// to Admin/Security Analyst (see app/threat_intel/router.py). Mirrored
// here so a Viewer or Network Administrator sees a clearly-disabled
// control with an explanation, instead of an enabled button that just
// 403s when clicked.
const CAN_SYNC_ROLES = new Set(["admin", "security_analyst"]);

export default function ThreatIntel() {
  const { user: me } = useAuth();
  const canSync = !!me && CAN_SYNC_ROLES.has(me.role);

  const [status, setStatus] = useState<ThreatIntelStatus | null>(null);
  const [items, setItems] = useState<Vulnerability[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("");
  const [cve, setCve] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [listLoading, setListLoading] = useState(false);

  async function load(nextOffset = offset) {
    setError(null);
    setListLoading(true);
    try {
      const [providerStatus, vulnerabilities] = await Promise.all([
        getThreatIntelStatus(),
        listVulnerabilities({
          search: search || undefined,
          severity: severity || undefined,
          limit: PAGE_SIZE,
          offset: nextOffset,
        }),
      ]);
      setStatus(providerStatus);
      setItems(vulnerabilities.items);
      setTotal(vulnerabilities.total);
      setOffset(nextOffset);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load threat intelligence.");
    } finally {
      setListLoading(false);
    }
  }

  useEffect(() => {
    load(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [severity]);

  async function handleSync(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    setError(null);
    if (!cve.trim()) return;
    setLoading(true);
    try {
      const result = await syncCVE(cve.trim());
      setMessage(`${result.cve_id} ${result.created ? "imported" : result.updated ? "updated" : "already current"}.`);
      setCve("");
      await load(0);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to sync CVE.");
    } finally {
      setLoading(false);
    }
  }

  const hasNextPage = offset + items.length < total;
  const hasPrevPage = offset > 0;

  return (
    <Layout>
      <div className="space-y-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Threat Intelligence</h1>
          <p className="mt-1 text-xs text-vexus-muted">
            VEXUS vulnerability intelligence. Imported CVEs become normalized threat-intelligence records and can enter the same event pipeline as other external telemetry.
          </p>
        </div>

        {error && <div className="rounded border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-400">{error}</div>}
        {message && <div className="rounded border border-vexus-border bg-vexus-accent/10 px-3 py-2 text-sm text-vexus-accent">{message}</div>}

        <div className="grid gap-4 md:grid-cols-3">
          <Card className="p-4 md:col-span-2">
            <div className="mb-3 text-xs uppercase tracking-wider text-vexus-muted">NVD synchronization</div>
            {canSync ? (
              <>
                <form onSubmit={handleSync} className="flex flex-col gap-2 sm:flex-row">
                  <input
                    value={cve}
                    onChange={(e) => setCve(e.target.value)}
                    placeholder="CVE-2026-12345"
                    className="min-w-0 flex-1 rounded border border-vexus-border bg-vexus-bg px-3 py-2 text-sm outline-none focus:border-vexus-accent"
                  />
                  <Button type="submit" disabled={loading || !status?.configured}>
                    {loading ? "Syncing…" : "Sync CVE"}
                  </Button>
                </form>
                <p className="mt-2 text-[11px] text-vexus-muted">
                  {status?.configured
                    ? "NVD adapter enabled."
                    : "NVD adapter is disabled. Set NVD_ENABLED=true in the backend environment to enable synchronization."}
                </p>
              </>
            ) : (
              <p className="text-xs text-vexus-muted">
                Syncing new CVE records requires the Admin or Security Analyst role. You can still search and review
                previously imported vulnerabilities below.
              </p>
            )}
          </Card>

          <Card className="p-4">
            <div className="text-xs uppercase tracking-wider text-vexus-muted">Provider</div>
            <div className="mt-2 text-lg font-medium">{status?.provider?.toUpperCase() || "—"}</div>
            <Badge value={status?.configured ? "configured" : "disabled"} />
          </Card>
        </div>

        <Card className="p-4">
          <div className="grid gap-3 md:grid-cols-3">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && load(0)}
              placeholder="Search CVE or description"
              className="rounded border border-vexus-border bg-vexus-bg px-3 py-2 text-sm outline-none focus:border-vexus-accent"
            />
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              className="rounded border border-vexus-border bg-vexus-bg px-3 py-2 text-sm outline-none focus:border-vexus-accent"
            >
              <option value="">All severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
            <Button type="button" onClick={() => load(0)}>Search</Button>
          </div>
        </Card>

        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-vexus-border text-xs text-vexus-muted">
              <tr>
                <th className="px-4 py-2 text-left">CVE</th>
                <th className="px-4 py-2 text-left">Severity</th>
                <th className="px-4 py-2 text-left">CVSS</th>
                <th className="px-4 py-2 text-left">Published</th>
                <th className="px-4 py-2 text-left">Source</th>
              </tr>
            </thead>
            <tbody>
              {listLoading && (
                <tr><td colSpan={5} className="py-8 text-center text-xs text-vexus-muted">Loading…</td></tr>
              )}
              {!listLoading && items.length === 0 && (
                <tr><td colSpan={5} className="py-8 text-center text-xs text-vexus-muted">No vulnerability records imported yet.</td></tr>
              )}
              {!listLoading && items.map((item) => {
                const expanded = expandedId === item.id;
                return (
                  <Fragment key={item.id}>
                    <tr
                      className="cursor-pointer border-b border-vexus-border last:border-0 hover:bg-white/[0.02]"
                      onClick={() => setExpandedId(expanded ? null : item.id)}
                    >
                      <td className="px-4 py-3">
                        <div className="font-medium">{item.cve_id}</div>
                        <div className="max-w-xl truncate text-[11px] text-vexus-muted">{item.description || "No description"}</div>
                      </td>
                      <td className="px-4 py-3"><Badge value={item.cvss_severity || "unknown"} /></td>
                      <td className="px-4 py-3 text-vexus-muted">{item.cvss_score ?? "—"} {item.cvss_version ? `(v${item.cvss_version})` : ""}</td>
                      <td className="px-4 py-3 text-xs text-vexus-muted">{item.published_at ? new Date(item.published_at).toLocaleDateString() : "—"}</td>
                      <td className="px-4 py-3 text-xs text-vexus-muted">{item.source}</td>
                    </tr>
                    {expanded && (
                      <tr className="border-b border-vexus-border last:border-0 bg-white/[0.015]">
                        <td colSpan={5} className="px-4 py-3">
                          <div className="grid gap-3 md:grid-cols-3 text-xs">
                            <div>
                              <div className="mb-1 text-vexus-muted uppercase tracking-wider">CWE</div>
                              {item.cwe_ids.length ? item.cwe_ids.join(", ") : "—"}
                            </div>
                            <div>
                              <div className="mb-1 text-vexus-muted uppercase tracking-wider">Affected CPEs</div>
                              {item.affected_cpes.length ? (
                                <ul className="space-y-0.5">
                                  {item.affected_cpes.slice(0, 5).map((cpe) => <li key={cpe} className="break-all">{cpe}</li>)}
                                  {item.affected_cpes.length > 5 && <li className="text-vexus-muted">+{item.affected_cpes.length - 5} more</li>}
                                </ul>
                              ) : "—"}
                            </div>
                            <div>
                              <div className="mb-1 text-vexus-muted uppercase tracking-wider">References</div>
                              {item.references.length ? (
                                <ul className="space-y-0.5">
                                  {item.references.slice(0, 3).map((ref) => (
                                    <li key={ref} className="truncate">
                                      <a href={ref} target="_blank" rel="noreferrer noopener" className="text-vexus-accent hover:underline">
                                        {ref}
                                      </a>
                                    </li>
                                  ))}
                                  {item.references.length > 3 && <li className="text-vexus-muted">+{item.references.length - 3} more</li>}
                                </ul>
                              ) : "—"}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t border-vexus-border px-4 py-2 text-xs text-vexus-muted">
            <span>
              {total > 0 ? `Showing ${offset + 1}–${offset + items.length} of ${total}` : "0 results"}
            </span>
            <div className="flex gap-2">
              <Button type="button" variant="secondary" disabled={!hasPrevPage || listLoading} onClick={() => load(Math.max(0, offset - PAGE_SIZE))}>
                Previous
              </Button>
              <Button type="button" variant="secondary" disabled={!hasNextPage || listLoading} onClick={() => load(offset + PAGE_SIZE)}>
                Next
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </Layout>
  );
}
