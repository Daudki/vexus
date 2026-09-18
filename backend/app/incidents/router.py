from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import require_any_role, require_role
from app.database.session import get_db
from app.incidents.models import IncidentStatus
from app.incidents.repository import IncidentRepository
from app.incidents.schemas import (
    IncidentCreate,
    IncidentDetailRead,
    IncidentRead,
    IncidentUpdate,
    LinkAlertRequest,
    LinkAssetRequest,
    NoteCreate,
    NoteRead,
    TimelineEntryRead,
)
from app.incidents.service import IncidentError, IncidentService
from app.users.models import RoleName, User

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])

_MANAGE_ROLES = (RoleName.ADMIN, RoleName.SECURITY_ANALYST, RoleName.NETWORK_ADMINISTRATOR)


def _get_incident_or_404(db: Session, incident_id: str):
    incident = IncidentRepository(db).get_by_id(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")
    return incident


def _to_detail(db: Session, incident) -> IncidentDetailRead:
    repo = IncidentRepository(db)
    alert_ids = [link.alert_id for link in repo.list_alert_links(incident.id)]
    asset_ids = [link.asset_id for link in repo.list_asset_links(incident.id)]
    return IncidentDetailRead(
        id=incident.id,
        title=incident.title,
        description=incident.description,
        severity=incident.severity,
        confidence=incident.confidence,
        status=incident.status,
        assigned_to=incident.assigned_to,
        resolution=incident.resolution,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        is_synthetic=incident.is_synthetic,
        alert_ids=alert_ids,
        asset_ids=asset_ids,
    )


@router.get("", response_model=list[IncidentRead])
def list_incidents(
    status_filter: IncidentStatus | None = None,
    include_synthetic: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_role),
) -> list[IncidentRead]:
    return IncidentRepository(db).list_all(status=status_filter, include_synthetic=include_synthetic)


@router.post("", response_model=IncidentDetailRead, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> IncidentDetailRead:
    service = IncidentService(db)
    try:
        incident = service.create_incident(
            title=payload.title,
            description=payload.description,
            alert_ids=payload.alert_ids,
            asset_ids=payload.asset_ids,
            severity=payload.severity,
            confidence=payload.confidence,
            actor=current_user,
            ip_address=request.client.host,
        )
    except IncidentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _to_detail(db, incident)


@router.get("/{incident_id}", response_model=IncidentDetailRead)
def get_incident(
    incident_id: str, db: Session = Depends(get_db), _: User = Depends(require_any_role)
) -> IncidentDetailRead:
    incident = _get_incident_or_404(db, incident_id)
    return _to_detail(db, incident)


@router.patch("/{incident_id}", response_model=IncidentDetailRead)
def update_incident(
    incident_id: str,
    payload: IncidentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> IncidentDetailRead:
    incident = _get_incident_or_404(db, incident_id)
    service = IncidentService(db)
    updated = service.update(
        incident,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        assigned_to=payload.assigned_to,
        resolution=payload.resolution,
        actor=current_user,
        ip_address=request.client.host,
    )
    return _to_detail(db, updated)


@router.get("/{incident_id}/timeline", response_model=list[TimelineEntryRead])
def get_timeline(
    incident_id: str, db: Session = Depends(get_db), _: User = Depends(require_any_role)
) -> list[TimelineEntryRead]:
    incident = _get_incident_or_404(db, incident_id)
    return IncidentService(db).get_timeline(incident)


@router.post("/{incident_id}/alerts", response_model=IncidentDetailRead)
def link_alert(
    incident_id: str,
    payload: LinkAlertRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> IncidentDetailRead:
    incident = _get_incident_or_404(db, incident_id)
    service = IncidentService(db)
    try:
        service.link_alert(incident, payload.alert_id, current_user, ip_address=request.client.host)
    except IncidentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _to_detail(db, incident)


@router.delete("/{incident_id}/alerts/{alert_id}", response_model=IncidentDetailRead)
def unlink_alert(
    incident_id: str,
    alert_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> IncidentDetailRead:
    incident = _get_incident_or_404(db, incident_id)
    service = IncidentService(db)
    try:
        service.unlink_alert(incident, alert_id, current_user, ip_address=request.client.host)
    except IncidentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _to_detail(db, incident)


@router.post("/{incident_id}/assets", response_model=IncidentDetailRead)
def link_asset(
    incident_id: str,
    payload: LinkAssetRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> IncidentDetailRead:
    incident = _get_incident_or_404(db, incident_id)
    service = IncidentService(db)
    try:
        service.link_asset(incident, payload.asset_id, current_user, ip_address=request.client.host)
    except IncidentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _to_detail(db, incident)


@router.post("/{incident_id}/notes", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def add_note(
    incident_id: str,
    payload: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_MANAGE_ROLES)),
) -> NoteRead:
    incident = _get_incident_or_404(db, incident_id)
    return IncidentService(db).add_note(incident, payload.content, current_user)


@router.get("/{incident_id}/notes", response_model=list[NoteRead])
def list_notes(
    incident_id: str, db: Session = Depends(get_db), _: User = Depends(require_any_role)
) -> list[NoteRead]:
    incident = _get_incident_or_404(db, incident_id)
    return IncidentRepository(db).list_notes(incident.id)
