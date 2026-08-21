from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.deps import require_any_role, require_role
from app.database.session import get_db
from app.discovery.collectors import DiscoveryCollector, NmapCollector
from app.discovery.models import ScanJob
from app.discovery.schemas import ScanRead, ScanRequest
from app.discovery.service import DiscoveryService
from app.users.models import RoleName, User

router = APIRouter(prefix="/api/v1/discovery", tags=["discovery"])


def get_discovery_collector() -> DiscoveryCollector:
    """Default collector for the running deployment. Overridden in tests
    to inject a SimulatedCollector instead of requiring nmap + network access."""
    return NmapCollector()


@router.post(
    "/scans",
    response_model=ScanRead,
    status_code=status.HTTP_201_CREATED,
)
def start_scan(
    payload: ScanRequest,
    request: Request,
    db: Session = Depends(get_db),
    collector: DiscoveryCollector = Depends(get_discovery_collector),
    current_user: User = Depends(require_role(RoleName.ADMIN, RoleName.NETWORK_ADMINISTRATOR)),
) -> ScanRead:
    service = DiscoveryService(db, collector)
    job = service.run_scan(payload.target_ranges, initiated_by=current_user, ip_address=request.client.host)

    if job.status.value == "refused":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=job.error_message)

    return job


@router.get("/scans", response_model=list[ScanRead])
def list_scans(
    db: Session = Depends(get_db),
    _: User = Depends(require_any_role),
) -> list[ScanRead]:
    query = select(ScanJob).order_by(desc(ScanJob.started_at)).limit(50)
    return list(db.scalars(query))


@router.get("/scans/{scan_id}", response_model=ScanRead)
def get_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_role),
) -> ScanRead:
    job = db.get(ScanJob, scan_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return job
