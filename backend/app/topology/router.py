from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import require_any_role, require_role
from app.database.session import get_db
from app.topology.repository import TopologyRepository
from app.topology.schemas import (
    GraphResponse,
    InferenceSummaryRead,
    InferSubnetRequest,
    RelationshipCreate,
    RelationshipRead,
)
from app.topology.service import TopologyError, TopologyService
from app.users.models import RoleName, User

router = APIRouter(prefix="/api/v1/topology", tags=["topology"])


@router.get("/graph", response_model=GraphResponse)
def get_graph(db: Session = Depends(get_db), _: User = Depends(require_any_role)) -> GraphResponse:
    return TopologyService(db).get_graph()


@router.get("/relationships", response_model=list[RelationshipRead])
def list_relationships(
    asset_id: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_role),
) -> list[RelationshipRead]:
    return TopologyRepository(db).list_all(asset_id=asset_id)


@router.post(
    "/relationships",
    response_model=RelationshipRead,
    status_code=status.HTTP_201_CREATED,
)
def create_relationship(
    payload: RelationshipCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(RoleName.ADMIN, RoleName.NETWORK_ADMINISTRATOR, RoleName.SECURITY_ANALYST)
    ),
) -> RelationshipRead:
    service = TopologyService(db)
    try:
        return service.create_manual_relationship(
            source_asset_id=payload.source_asset_id,
            target_asset_id=payload.target_asset_id,
            relationship_type=payload.relationship_type,
            description=payload.description,
            actor=current_user,
            ip_address=request.client.host,
        )
    except TopologyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(
    relationship_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(RoleName.ADMIN, RoleName.NETWORK_ADMINISTRATOR, RoleName.SECURITY_ANALYST)
    ),
) -> None:
    service = TopologyService(db)
    try:
        service.delete_relationship(relationship_id, actor=current_user, ip_address=request.client.host)
    except TopologyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/infer-subnet", response_model=InferenceSummaryRead)
def infer_subnet(
    payload: InferSubnetRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN, RoleName.NETWORK_ADMINISTRATOR)),
) -> InferenceSummaryRead:
    service = TopologyService(db)
    return service.infer_subnet_relationships(
        prefix_length=payload.prefix_length, actor=current_user, ip_address=request.client.host
    )
