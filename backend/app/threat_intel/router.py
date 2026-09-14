from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.deps import require_any_role, require_role
from app.core.rate_limit import limiter
from app.database.session import get_db
from app.threat_intel.provider import NVDProvider, ThreatIntelProviderError
from app.threat_intel.repository import VulnerabilityRepository
from app.threat_intel.schemas import SyncCVEResponse, ThreatIntelStatus, VulnerabilityListResponse, VulnerabilityRead
from app.threat_intel.service import ThreatIntelService
from app.users.models import RoleName, User

router = APIRouter(prefix="/api/v1/threat-intel", tags=["threat-intelligence"])


def _provider() -> NVDProvider:
    settings = get_settings()
    return NVDProvider(
        base_url=settings.NVD_API_URL,
        api_key=settings.NVD_API_KEY,
        timeout_seconds=settings.NVD_TIMEOUT_SECONDS,
    )


@router.get("/status", response_model=ThreatIntelStatus)
def status_endpoint(_: User = Depends(require_any_role)) -> ThreatIntelStatus:
    settings = get_settings()
    return ThreatIntelStatus(provider="nvd", configured=bool(settings.NVD_ENABLED))


@router.get("/vulnerabilities", response_model=VulnerabilityListResponse)
def list_vulnerabilities(
    search: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_role),
) -> VulnerabilityListResponse:
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    rows, total = VulnerabilityRepository(db).list(search=search, severity=severity, limit=limit, offset=offset)
    return VulnerabilityListResponse(items=[ThreatIntelService.to_read(row) for row in rows], total=total)


@router.get("/vulnerabilities/{cve_id}", response_model=VulnerabilityRead)
def get_vulnerability(cve_id: str, db: Session = Depends(get_db), _: User = Depends(require_any_role)) -> VulnerabilityRead:
    vulnerability = VulnerabilityRepository(db).get_by_cve(cve_id)
    if vulnerability is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vulnerability not found.")
    return ThreatIntelService.to_read(vulnerability)


@router.post("/sync/cve/{cve_id}", response_model=SyncCVEResponse)
@limiter.limit(get_settings().THREAT_INTEL_SYNC_RATE_LIMIT)
def sync_cve(
    cve_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN, RoleName.SECURITY_ANALYST)),
) -> SyncCVEResponse:
    settings = get_settings()
    if not settings.NVD_ENABLED:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="NVD threat intelligence is disabled.")
    try:
        vulnerability, created, updated, event_id = ThreatIntelService(db, _provider()).sync_cve(
            cve_id, actor=current_user, ip_address=request.client.host
        )
    except ThreatIntelProviderError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return SyncCVEResponse(
        cve_id=vulnerability.cve_id,
        created=created,
        updated=updated,
        event_id=event_id,
        source=vulnerability.source,
    )
