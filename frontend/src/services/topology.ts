import { apiRequest } from "./api";

export type RelationshipConfidence = "confirmed" | "inferred" | "unknown";

export interface GraphNode {
  id: string;
  hostname: string | null;
  ip_address: string | null;
  device_type: string | null;
  status: string;
  criticality: string;
  trust_status: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  confidence: RelationshipConfidence;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface InferenceSummary {
  subnets_examined: number;
  relationships_created: number;
  relationships_updated: number;
}

export function fetchGraph(): Promise<GraphResponse> {
  return apiRequest<GraphResponse>("/topology/graph");
}

export function createRelationship(
  sourceAssetId: string,
  targetAssetId: string,
  relationshipType: string,
  description: string
) {
  return apiRequest("/topology/relationships", {
    method: "POST",
    body: JSON.stringify({
      source_asset_id: sourceAssetId,
      target_asset_id: targetAssetId,
      relationship_type: relationshipType,
      description,
    }),
  });
}

export function deleteRelationship(relationshipId: string) {
  return apiRequest(`/topology/relationships/${relationshipId}`, { method: "DELETE" });
}

export function inferSubnetRelationships(prefixLength = 24): Promise<InferenceSummary> {
  return apiRequest<InferenceSummary>("/topology/infer-subnet", {
    method: "POST",
    body: JSON.stringify({ prefix_length: prefixLength }),
  });
}
