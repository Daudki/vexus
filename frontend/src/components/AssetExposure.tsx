import { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../services/api";
import { AssetServiceItem, getAssetServices } from "../services/assets";
import {
  AssetVulnerabilityLink,
  linkAssetVulnerability,
  listAssetVulnerabilities,
  runVulnerabilityMatching,
  unlinkAssetVulnerability,
} from "../services/threatIntel";
import Badge from "./ui/Badge";
import Button from "./ui/Button";
import Card from "./ui/Card";
import { Input } from "./ui/Form";

const MANAGE_ROLES = ["admin", "security_analyst"];
const CVE_PATTERN = /^CVE-\d{4}-\d{4,}$/i;

const SOURCE_LABEL: Record<string, string> = {
  manual: "analyst",
  cpe_match: "auto-match",
};

interface Props {
  assetId: string;
  onLinksChanged?: () => void | Promise<void>;
}

export default function AssetExposure({ assetId, onLinksChanged }: Props) {
  const { user } = useAuth();
  const canManage = user ? MANAGE_ROLES.includes(user.role) : false;

  const [services, setServices] = useState<AssetServiceItem[]>([]);
  const [links, setLinks] = useState<AssetVulnerabilityLink[]>([]);
  const [cveInput, setCveInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function load() {
    try {
      const [serviceData, linkData] = await Promise.all([getAssetServices(assetId), listAssetVulnerabilities(assetId)]);
      setServices(serviceData);
      setLinks(linkData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load exposure data.");
    }
  }

  useEffect(() => {
    load();
  }, [assetId]);

  async function afterChange() {
    await load();
    if (onLinksChanged) await onLinksChanged();
  }

  async function handleLink(e: React.FormEvent) {
    e.preventDefault();
    const cveId = cveInput.trim().toUpperCase();
    setError(null);
    setNotice(null);
    if (!CVE_PATTERN.test(cveId)) {
      setError("Enter a CVE ID like CVE-2024-6387.");
      return;
    }
    setBusy(true);
    try {
      await linkAssetVulnerability(assetId, cveId);
      setCveInput("");
      await afterChange();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to link CVE.");
    } finally {
      setBusy(false);
    }
  }

  async function handleUnlink(cveId: string) {
    if (!window.confirm(`Unlink ${cveId} from this asset?`)) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await unlinkAssetVulnerability(assetId, cveId);
      await afterChange();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to unlink CVE.");
    } finally {
      setBusy(false);
    }
  }

  async function handleMatch() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const summary = await runVulnerabilityMatching();
      setNotice(
        `Matched ${summary.assets_evaluated} asset(s): ${summary.links_created} linked, ${summary.links_removed} removed.`
      );
      await afterChange();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Matching failed.");
    } finally {
      setBusy(false);
    }
  }

  const unmatchable = services.filter((s) => !s.cpe).length;

  return (
    <Card className="p-4 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-vexus-muted">Exposure</h2>
        {canManage && (
          <Button variant="secondary" onClick={handleMatch} disabled={busy}>
            Run CVE matching
          </Button>
        )}
      </div>

      {error && <div className="text-sm text-red-400 bg-red-950/40 border border-red-900 rounded px-3 py-2">{error}</div>}
      {notice && (
        <div className="text-sm text-blue-300 bg-blue-950/40 border border-blue-900 rounded px-3 py-2">{notice}</div>
      )}

      <section className="space-y-2">
        <h3 className="text-xs font-medium text-vexus-text">Linked vulnerabilities</h3>
        {links.length === 0 && <p className="text-xs text-vexus-muted">No CVEs are linked to this asset.</p>}
        <ul className="space-y-1.5">
          {links.map((link) => (
            <li
              key={link.id}
              className="flex items-center justify-between gap-3 text-sm border-b border-vexus-border last:border-0 pb-1.5"
            >
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono">{link.cve_id}</span>
                {link.cvss_severity ? (
                  <Badge value={link.cvss_severity.toLowerCase()} />
                ) : (
                  <span className="text-xs text-vexus-muted">unscored</span>
                )}
                {link.cvss_score !== null && <span className="text-xs text-vexus-muted">CVSS {link.cvss_score}</span>}
                <Badge value={link.confidence} />
                <span className="text-xs text-vexus-muted">{SOURCE_LABEL[link.match_source] ?? link.match_source}</span>
                {link.is_rejected && <span className="text-xs text-yellow-400">rejected by NVD, not scored</span>}
              </div>
              {canManage && (
                <Button variant="ghost" onClick={() => handleUnlink(link.cve_id)} disabled={busy}>
                  Unlink
                </Button>
              )}
            </li>
          ))}
        </ul>
        {canManage && (
          <form onSubmit={handleLink} className="flex gap-2 pt-1">
            <Input
              value={cveInput}
              onChange={(e) => setCveInput(e.target.value)}
              placeholder="CVE-2024-6387"
              disabled={busy}
            />
            <Button type="submit" disabled={busy || !cveInput.trim()}>
              Link
            </Button>
          </form>
        )}
        {canManage && (
          <p className="text-xs text-vexus-muted">The CVE must already be synced from Threat Intel before it can be linked.</p>
        )}
      </section>

      <section className="space-y-2">
        <h3 className="text-xs font-medium text-vexus-text">Detected services</h3>
        {services.length === 0 ? (
          <p className="text-xs text-vexus-muted">
            No services recorded. Run a Discovery scan with the Service version profile to detect products and versions.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-vexus-muted">
                  <th className="py-1 pr-4 font-normal">Port</th>
                  <th className="py-1 pr-4 font-normal">Service</th>
                  <th className="py-1 pr-4 font-normal">Product</th>
                  <th className="py-1 font-normal">Version</th>
                </tr>
              </thead>
              <tbody>
                {services.map((svc) => (
                  <tr key={svc.id} className="border-t border-vexus-border">
                    <td className="py-1 pr-4">
                      {svc.port}/{svc.protocol}
                    </td>
                    <td className="py-1 pr-4">{svc.name || <span className="text-vexus-muted">—</span>}</td>
                    <td className="py-1 pr-4">{svc.product || <span className="text-vexus-muted">—</span>}</td>
                    <td className="py-1">
                      {svc.version || <span className="text-vexus-muted">—</span>}
                      {!svc.cpe && <span className="ml-2 text-xs text-vexus-muted">not matchable</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {unmatchable > 0 && (
          <p className="text-xs text-vexus-muted">
            {unmatchable} service(s) have no CPE from nmap, so they can't be matched to CVEs automatically.
          </p>
        )}
      </section>
    </Card>
  );
}
