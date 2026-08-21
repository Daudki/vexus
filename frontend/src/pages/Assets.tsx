import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import Badge from "../components/ui/Badge";
import Card from "../components/ui/Card";
import { Field, Input, Select } from "../components/ui/Form";
import { ApiError } from "../services/api";
import { Asset, listAssets } from "../services/assets";

export default function Assets() {
  const navigate = useNavigate();
  const [assets, setAssets] = useState<Asset[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [trustStatus, setTrustStatus] = useState("");
  const [criticality, setCriticality] = useState("");
  const [sortBy, setSortBy] = useState("last_seen");

  async function load() {
    setError(null);
    try {
      const results = await listAssets({
        search: search || undefined,
        status: status || undefined,
        trust_status: trustStatus || undefined,
        criticality: criticality || undefined,
        sort_by: sortBy,
        sort_desc: true,
        limit: 100,
      });
      setAssets(results);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load assets.");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, trustStatus, criticality, sortBy]);

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    load();
  }

  return (
    <Layout>
      <div className="space-y-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Assets</h1>
          <p className="text-xs text-vexus-muted mt-1">
            The full inventory VEXUS has observed. A new device is always shown as "unknown" trust,
            never assumed untrusted — an analyst decides that.
          </p>
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-950/40 border border-red-900 rounded px-3 py-2">{error}</div>
        )}

        <Card className="p-4">
          <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 md:grid-cols-5 gap-3">
            <Field label="Search (hostname or IP)">
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="e.g. printer, 10.0.0.5" />
            </Field>
            <Field label="Status">
              <Select value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">All</option>
                <option value="online">Online</option>
                <option value="offline">Offline</option>
                <option value="unknown">Unknown</option>
              </Select>
            </Field>
            <Field label="Trust">
              <Select value={trustStatus} onChange={(e) => setTrustStatus(e.target.value)}>
                <option value="">All</option>
                <option value="trusted">Trusted</option>
                <option value="unknown">Unknown</option>
                <option value="untrusted">Untrusted</option>
              </Select>
            </Field>
            <Field label="Criticality">
              <Select value={criticality} onChange={(e) => setCriticality(e.target.value)}>
                <option value="">All</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </Select>
            </Field>
            <Field label="Sort by">
              <Select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                <option value="last_seen">Last seen</option>
                <option value="first_seen">First seen</option>
                <option value="risk_score">Risk score</option>
                <option value="hostname">Hostname</option>
              </Select>
            </Field>
          </form>
        </Card>

        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="text-xs text-vexus-muted border-b border-vexus-border">
              <tr>
                <th className="text-left px-4 py-2">Hostname</th>
                <th className="text-left px-4 py-2">IP address</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-left px-4 py-2">Trust</th>
                <th className="text-left px-4 py-2">Criticality</th>
                <th className="text-left px-4 py-2">Last seen</th>
              </tr>
            </thead>
            <tbody>
              {assets === null && (
                <tr>
                  <td colSpan={6} className="text-center text-vexus-muted text-xs py-6">
                    Loading…
                  </td>
                </tr>
              )}
              {assets?.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-center text-vexus-muted text-xs py-6">
                    No assets match these filters. Run a discovery scan from the Discovery page to populate the inventory.
                  </td>
                </tr>
              )}
              {assets?.map((asset) => (
                <tr
                  key={asset.id}
                  onClick={() => navigate(`/assets/${asset.id}`)}
                  className="border-b border-vexus-border last:border-0 cursor-pointer hover:bg-vexus-border/20"
                >
                  <td className="px-4 py-2">{asset.hostname || <span className="text-vexus-muted">—</span>}</td>
                  <td className="px-4 py-2 text-vexus-muted">{asset.ip_address || "—"}</td>
                  <td className="px-4 py-2">
                    <Badge value={asset.status} />
                  </td>
                  <td className="px-4 py-2">
                    <Badge value={asset.trust_status} />
                  </td>
                  <td className="px-4 py-2">
                    <Badge value={asset.criticality} />
                  </td>
                  <td className="px-4 py-2 text-vexus-muted text-xs">
                    {new Date(asset.last_seen).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </Layout>
  );
}
