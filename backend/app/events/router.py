"""
External event ingestion boundary (syslog / threat-intel / manual).

Authorization note: VEXUS has no separate service-account/API-key auth
primitive yet, so this reuses the same bearer-JWT RBAC as every other
endpoint rather than inventing a second auth mechanism (VEXUS v2
Development Rules, "do not introduce a second implementation of the
same subsystem"). In practice this means a syslog forwarder or
threat-intel feed should authenticate with a dedicated service account
issued a normal login token, not a personal analyst account. A
dedicated ingestion API-key model is a reasonable future enhancement,
not assumed here.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.database.session import get_db
from app.events.schemas import EventIngestBatch, EventIngestResponse
from app.events.service import EventIngestionError, EventIngestionService
from app.users.models import RoleName, User

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.post("/ingest", response_model=EventIngestResponse)
def ingest_events(
    payload: EventIngestBatch,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN, RoleName.SECURITY_ANALYST, RoleName.NETWORK_ADMINISTRATOR)),
) -> EventIngestResponse:
    service = EventIngestionService(db)
    try:
        results = service.ingest_batch(payload.events, actor=current_user, ip_address=request.client.host)
    except EventIngestionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    unmatched = sum(1 for _, matched in results if not matched)
    return EventIngestResponse(
        ingested_count=len(results),
        unmatched_asset_count=unmatched,
        results=[EventIngestionService.to_result(event, matched) for event, matched in results],
    )
