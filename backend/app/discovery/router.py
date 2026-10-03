import shutil

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.deps import require_any_role, require_role
from app.config.settings import get_settings
from app.database.session import get_db
from app.discovery.collectors import (
    DEFAULT_TIMING_TEMPLATE,
    DiscoveryCollector,
    NmapCollector,
    PythonTcpCollector,
    ScanProfile,
)
from app.discovery.models import ScanJob
from app.discovery.schemas import ScanRead, ScanRequest
from app.discovery.service import DiscoveryService
from app.users.models import RoleName, User

router = APIRouter(prefix="/api/v1/discovery", tags=["discovery"])


def _resolve_profile(profile: ScanProfile | None) -> ScanProfile:
    """Pick the actual profile for a scan. Caller-supplied wins; the
    platform default (Settings.DISCOVERY_DEFAULT_PROFILE) is the fallback."""
    if profile is not None:
        return profile
    settings = get_settings()
    try:
        return ScanProfile(settings.DISCOVERY_DEFAULT_PROFILE)
    except ValueError as exc:
        raise ValueError(
            f"DISCOVERY_DEFAULT_PROFILE='{settings.DISCOVERY_DEFAULT_PROFILE}' is not a "
            f"valid ScanProfile. Valid values: {[p.value for p in ScanProfile]}."
        ) from exc


def get_discovery_collector() -> DiscoveryCollector:
    """Default collector for the running deployment. Overridden in tests
    to inject a SimulatedCollector instead of requiring nmap + network access."""
    settings = get_settings()
    if settings.DISCOVERY_COLLECTOR == "python":
        return PythonTcpCollector(
            ports=settings.discovery_ports_list,
            timeout_seconds=settings.DISCOVERY_TIMEOUT_SECONDS,
            max_workers=settings.DISCOVERY_MAX_WORKERS,
        )
    if settings.DISCOVERY_COLLECTOR == "nmap":
        return NmapCollector(profile=_resolve_profile(None))
    if shutil.which("nmap") is not None:
        return NmapCollector(profile=_resolve_profile(None))
    return PythonTcpCollector(
        ports=settings.discovery_ports_list,
        timeout_seconds=settings.DISCOVERY_TIMEOUT_SECONDS,
        max_workers=settings.DISCOVERY_MAX_WORKERS,
    )


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
    # Resolve the profile once, here, so a malformed default is surfaced
    # as a 400 to the caller rather than crashing the worker.
    try:
        resolved_profile = _resolve_profile(payload.profile)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # If the dependency-injected collector is an NmapCollector, attach
    # the caller-supplied profile so the nmap subprocess gets the right
    # flags for THIS scan (the dependency default is the platform
    # default; the per-request profile wins here).
    if isinstance(collector, NmapCollector) and payload.profile is not None:
        collector = NmapCollector(profile=payload.profile, extra_args=collector.extra_args)

    service = DiscoveryService(db, collector)
    job = service.run_scan(
        payload.target_ranges,
        initiated_by=current_user,
        ip_address=request.client.host,
        profile=resolved_profile,
    )

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
