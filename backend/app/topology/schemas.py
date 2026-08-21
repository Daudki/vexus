from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.topology.models import RelationshipConfidence


class RelationshipCreate(BaseModel):
    source_asset_id: str
    target_asset_id: str
    relationship_type: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=512)


class RelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_asset_id: str
    target_asset_id: str
    relationship_type: str
    confidence: RelationshipConfidence
    description: str
    first_observed: datetime
    last_observed: datetime


class InferSubnetRequest(BaseModel):
    prefix_length: int = Field(default=24, ge=8, le=30)


class InferenceSummaryRead(BaseModel):
    subnets_examined: int
    relationships_created: int
    relationships_updated: int


class GraphNode(BaseModel):
    id: str
    hostname: str | None
    ip_address: str | None
    device_type: str | None
    status: str
    criticality: str
    trust_status: str


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship_type: str
    confidence: RelationshipConfidence


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
