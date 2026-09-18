from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.alerts.models import AlertStatus
from app.alerts.repository import AlertRepository
from app.alerts.schemas import AlertRead, AlertUpdate
from app.alerts.service import AlertService
from app.core.deps import require_any_role, require_role
from app.database.session import get_db
from app.events.models import EventSeverity
from app.users.models import RoleName, User
from app.users.repository import UserRepository

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertRead])
def list_alerts(
    status_filter: AlertStatus | None = None,
    severity: EventSeverity | None = None,
    asset_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    include_synthetic: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_role),
) -> list[AlertRead]:
    repo = AlertRepository(db)
    return repo.list_alerts(
        status=status_filter,
        severity=severity.value if severity else None,
        asset_id=asset_id,
        limit=limit,
        offset=offset,
        include_synthetic=include_synthetic,
    )


@router.get("/{alert_id}", response_model=AlertRead)
def get_alert(alert_id: str, db: Session = Depends(get_db), _: User = Depends(require_any_role)) -> AlertRead:
    alert = AlertRepository(db).get_by_id(alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
    return alert


@router.patch("/{alert_id}", response_model=AlertRead)
def update_alert(
    alert_id: str,
    payload: AlertUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(RoleName.ADMIN, RoleName.SECURITY_ANALYST, RoleName.NETWORK_ADMINISTRATOR)
    ),
) -> AlertRead:
    repo = AlertRepository(db)
    alert = repo.get_by_id(alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")

    if payload.assigned_to is not None and UserRepository(db).get_by_id(payload.assigned_to) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned user not found.")

    return AlertService(db).update_status(
        alert,
        status=payload.status,
        assigned_to=payload.assigned_to,
        actor=current_user,
        ip_address=request.client.host,
    )
