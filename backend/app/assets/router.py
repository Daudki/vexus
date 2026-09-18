from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.assets.repository import AssetRepository
from app.assets.schemas import AssetHistoryRead, AssetListParams, AssetRead, AssetUpdate
from app.assets.service import AssetService
from app.audit.service import AuditService
from app.core.deps import require_any_role, require_role
from app.database.session import get_db
from app.users.models import RoleName, User

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


@router.get("", response_model=list[AssetRead])
def list_assets(
    params: AssetListParams = Depends(),
    db: Session = Depends(get_db),
    _: User = Depends(require_any_role),
) -> list[AssetRead]:
    repo = AssetRepository(db)
    assets, _total = repo.list_assets(
        search=params.search,
        status=params.status,
        trust_status=params.trust_status,
        criticality=params.criticality,
        sort_by=params.sort_by,
        sort_desc=params.sort_desc,
        limit=params.limit,
        offset=params.offset,
        include_synthetic=params.include_synthetic,
    )
    return assets


@router.get("/{asset_id}", response_model=AssetRead)
def get_asset(
    asset_id: str, db: Session = Depends(get_db), _: User = Depends(require_any_role)
) -> AssetRead:
    asset = AssetRepository(db).get_by_id(asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    return asset


@router.get("/{asset_id}/history", response_model=list[AssetHistoryRead])
def get_asset_history(
    asset_id: str, db: Session = Depends(get_db), _: User = Depends(require_any_role)
) -> list[AssetHistoryRead]:
    repo = AssetRepository(db)
    if repo.get_by_id(asset_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    return repo.get_history(asset_id)


@router.patch("/{asset_id}", response_model=AssetRead)
def update_asset(
    asset_id: str,
    payload: AssetUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(RoleName.ADMIN, RoleName.SECURITY_ANALYST, RoleName.NETWORK_ADMINISTRATOR)
    ),
) -> AssetRead:
    repo = AssetRepository(db)
    asset = repo.get_by_id(asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    updated = AssetService(db).update_metadata(
        asset,
        device_type=payload.device_type,
        owner=payload.owner,
        criticality=payload.criticality,
        trust_status=payload.trust_status,
    )

    AuditService(db).record(
        action="asset.update",
        actor=current_user,
        target_type="asset",
        target_id=asset_id,
        detail=payload.model_dump_json(exclude_none=True),
        ip_address=request.client.host,
    )

    return updated
