import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import { Field, Input, Select } from "../components/ui/Form";
import { useAuth } from "../hooks/useAuth";
import { ApiError } from "../services/api";
import {
  GraphResponse,
  createRelationship,
  deleteRelationship,
  fetchGraph,
  inferSubnetRelationships,
} from "../services/topology";

const CAN_EDIT_ROLES = ["admin", "network_administrator", "security_analyst"];
const CAN_INFER_ROLES = ["admin", "network_administrator"];

function assetLabel(graph: GraphResponse, assetId: string): string {
  const node = graph.nodes.find((n) => n.id === assetId);
  if (!node) return assetId;
  return node.hostname || node.ip_address || assetId;
}

export default function Topology() {
  const { user } = useAuth();
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [sourceId, setSourceId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [relType, setRelType] = useState("uplink");
  const [description, setDescription] = useState("");

  const canEdit = user ? CAN_EDIT_ROLES.includes(user.role) : false;
  const canInfer = user ? CAN_INFER_ROLES.includes(user.role) : false;

  async function reload() {
    try {
      setGraph(await fetchGraph());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load topology.");
    }
  }

  useEffect(() => {
    reload();
  }, []);

  async function handleCreateRelationship(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createRelationship(sourceId, targetId, relType, description);
      setSourceId("");
      setTargetId("");
      setDescription("");
      setNotice("Relationship created.");
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create relationship.");
    }
  }

  async function handleDelete(id: string) {
    setError(null);
    try {
      await deleteRelationship(id);
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete relationship.");
    }
  }

  async function handleInfer() {
    setError(null);
    setNotice(null);
    try {
      const summary = await inferSubnetRelationships(24);
      setNotice(
        `Subnet inference: ${summary.subnets_examined} subnets examined, ` +
          `${summary.relationships_created} created, ${summary.relationships_updated} updated.`
      );
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Subnet inference failed.");
    }
  }

  if (!graph) {
    return (
      <Layout>
        <div className="text-sm text-vexus-muted">Loading…</div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Nexus — Topology</h1>
          <p className="text-xs text-vexus-muted mt-1 max-w-2xl">
            A confirmed link means an analyst asserted it; an inferred link was computed from real
            observed data (currently: shared IP subnet). Nothing here is fabricated — VEXUS
            doesn't capture traffic yet, so "communicates with" edges aren't shown because there's
            no evidence for them.
          </p>
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-950/40 border border-red-900 rounded px-3 py-2">{error}</div>
        )}
        {notice && (
          <div className="text-sm text-blue-300 bg-blue-950/40 border border-blue-900 rounded px-3 py-2">{notice}</div>
        )}

        <Card className="flex items-center justify-between p-4">
          <div className="text-xs text-vexus-muted">
            {graph.nodes.length} assets · {graph.edges.length} relationships
          </div>
          {canInfer && <Button onClick={handleInfer}>Run subnet inference</Button>}
        </Card>

        {canEdit && (
          <Card className="p-4">
            <form onSubmit={handleCreateRelationship} className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
              <Field label="Source asset">
                <Select value={sourceId} onChange={(e) => setSourceId(e.target.value)} required>
                  <option value="">Select…</option>
                  {graph.nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.hostname || n.ip_address || n.id}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Target asset">
                <Select value={targetId} onChange={(e) => setTargetId(e.target.value)} required>
                  <option value="">Select…</option>
                  {graph.nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.hostname || n.ip_address || n.id}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Type">
                <Input
                  value={relType}
                  onChange={(e) => setRelType(e.target.value)}
                  placeholder="uplink, downlink, manual_link…"
                  required
                />
              </Field>
              <Field label="Description">
                <Input value={description} onChange={(e) => setDescription(e.target.value)} />
              </Field>
              <Button type="submit">Add manual link</Button>
            </form>
          </Card>
        )}

        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="text-xs text-vexus-muted border-b border-vexus-border">
              <tr>
                <th className="text-left px-4 py-2">Source</th>
                <th className="text-left px-4 py-2">Target</th>
                <th className="text-left px-4 py-2">Type</th>
                <th className="text-left px-4 py-2">Confidence</th>
                {canEdit && <th className="px-4 py-2"></th>}
              </tr>
            </thead>
            <tbody>
              {graph.edges.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center text-vexus-muted text-xs py-6">
                    No relationships yet. Add one manually or run subnet inference.
                  </td>
                </tr>
              )}
              {graph.edges.map((edge) => (
                <tr key={edge.id} className="border-b border-vexus-border last:border-0">
                  <td className="px-4 py-2">{assetLabel(graph, edge.source)}</td>
                  <td className="px-4 py-2">{assetLabel(graph, edge.target)}</td>
                  <td className="px-4 py-2 text-vexus-muted">{edge.relationship_type}</td>
                  <td className="px-4 py-2">
                    <Badge value={edge.confidence} />
                  </td>
                  {canEdit && (
                    <td className="px-4 py-2 text-right">
                      <button onClick={() => handleDelete(edge.id)} className="text-xs text-red-400 hover:text-red-300">
                        Remove
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </Layout>
  );
}
