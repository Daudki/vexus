from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.core.deps import require_any_role, require_role
from app.database.session import get_db
from app.detection.repository import DetectionRuleConfigRepository
from app.detection.schemas import (
    DetectionRuleCatalog,
    DetectionRuleConfigRead,
    DetectionRuleConfigUpdate,
    DetectionRunSummaryRead,
)
from app.detection.service import DetectionEngine
from app.users.models import RoleName, User

router = APIRouter(prefix="/api/v1/detection", tags=["detection"])


@router.post("/run", response_model=DetectionRunSummaryRead)
def trigger_run(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN, RoleName.SECURITY_ANALYST)),
) -> DetectionRunSummaryRead:
    engine = DetectionEngine(db)
    return engine.run(actor=current_user, ip_address=request.client.host)


@router.get("/rules", response_model=list[DetectionRuleConfigRead])
def list_rules(db: Session = Depends(get_db), _: User = Depends(require_any_role)) -> list[DetectionRuleConfigRead]:
    engine = DetectionEngine(db)
    # Ensure every registered rule has a config row (get-or-create with
    # defaults) so the list is complete even before the first run.
    for rule in engine.rules:
        engine.get_or_create_config(rule.rule_key)
    return DetectionRuleConfigRepository(db).list_all()


@router.get("/rules/catalog", response_model=DetectionRuleCatalog)
def get_catalog(_: User = Depends(require_any_role)) -> DetectionRuleCatalog:
    return DetectionRuleCatalog()


@router.patch("/rules/{rule_key}", response_model=DetectionRuleConfigRead)
def update_rule(
    rule_key: str,
    payload: DetectionRuleConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN, RoleName.SECURITY_ANALYST)),
) -> DetectionRuleConfigRead:
    repo = DetectionRuleConfigRepository(db)
    config = repo.get_by_rule_key(rule_key)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule config not found.")

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        return config

    updated = repo.update(config, **updates)

    AuditService(db).record(
        action="detection.rule_config_updated",
        actor=current_user,
        target_type="detection_rule_config",
        target_id=config.id,
        detail=f"{rule_key}: {updates}",
        ip_address=request.client.host,
    )
    return updated
