from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.assets.repository import AssetRepository
from app.core.deps import require_any_role, require_role
from app.database.session import get_db
from app.risk.repository import RiskRepository
from app.risk.schemas import (
    RecomputeSummaryRead,
    RiskScoreHistoryEntry,
    RiskScoreRead,
    TopRiskAssetRead,
)
from app.risk.service import RiskEngine
from app.users.models import RoleName, User

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


@router.post("/recompute", response_model=RecomputeSummaryRead)
def recompute_all(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN, RoleName.SECURITY_ANALYST)),
) -> RecomputeSummaryRead:
    engine = RiskEngine(db)
    return engine.recompute_all(actor=current_user, ip_address=request.client.host)


@router.post("/assets/{asset_id}/recompute", response_model=RiskScoreRead)
def recompute_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN, RoleName.SECURITY_ANALYST)),
) -> RiskScoreRead:
    asset = AssetRepository(db).get_by_id(asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    engine = RiskEngine(db)
    risk_score = engine.compute_for_asset(asset)
    factors = engine.repo.get_factors(risk_score.id)
    return RiskScoreRead(
        id=risk_score.id,
        asset_id=risk_score.asset_id,
        score=risk_score.score,
        risk_level=risk_score.risk_level,
        computed_at=risk_score.computed_at,
        factors=factors,
    )


@router.get("/assets/{asset_id}", response_model=RiskScoreRead)
def get_asset_risk(
    asset_id: str, db: Session = Depends(get_db), _: User = Depends(require_any_role)
) -> RiskScoreRead:
    repo = RiskRepository(db)
    if AssetRepository(db).get_by_id(asset_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    latest = repo.get_latest_for_asset(asset_id)
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No risk score has been computed for this asset yet. Trigger a recompute first.",
        )

    factors = repo.get_factors(latest.id)
    return RiskScoreRead(
        id=latest.id,
        asset_id=latest.asset_id,
        score=latest.score,
        risk_level=latest.risk_level,
        computed_at=latest.computed_at,
        factors=factors,
    )


@router.get("/assets/{asset_id}/history", response_model=list[RiskScoreHistoryEntry])
def get_asset_risk_history(
    asset_id: str, db: Session = Depends(get_db), _: User = Depends(require_any_role)
) -> list[RiskScoreHistoryEntry]:
    if AssetRepository(db).get_by_id(asset_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    return RiskRepository(db).get_history_for_asset(asset_id)


@router.get("/top", response_model=list[TopRiskAssetRead])
def get_top_risk_assets(
    limit: int = 10, db: Session = Depends(get_db), _: User = Depends(require_any_role)
) -> list[TopRiskAssetRead]:
    assets = RiskRepository(db).get_top_risk_assets(limit)
    return [
        TopRiskAssetRead(
            id=a.id,
            hostname=a.hostname,
            ip_address=a.ip_address,
            risk_score=a.risk_score,
            criticality=a.criticality.value,
            trust_status=a.trust_status.value,
        )
        for a in assets
    ]
