from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import require_any_role, require_role
from app.database.session import get_db
from app.simulation.schemas import SimulationResetRead, SimulationRunRead, SimulationStatusRead
from app.simulation.service import SimulationResetError, SimulationService
from app.users.models import RoleName, User

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


@router.get("/status", response_model=SimulationStatusRead)
def get_status(db: Session = Depends(get_db), _: User = Depends(require_any_role)) -> SimulationStatusRead:
    result = SimulationService(db).status()
    return SimulationStatusRead(**result.__dict__)


@router.post("/run", response_model=SimulationRunRead)
def run_scenario(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
) -> SimulationRunRead:
    """Creates simulated assets/events and immediately runs detection
    against them, so the demo is visible right away. Admin-only: this
    writes real rows across multiple tables, not a read-only preview."""
    result = SimulationService(db).run_scenario(actor=current_user, ip_address=request.client.host)
    return SimulationRunRead(
        assets_created=result.assets_created,
        events_created=result.events_created,
        alerts_created=result.alerts_created,
        alerts_updated=result.alerts_updated,
    )


@router.post("/reset", response_model=SimulationResetRead)
def reset_scenario(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
) -> SimulationResetRead:
    try:
        result = SimulationService(db).reset(actor=current_user, ip_address=request.client.host)
    except SimulationResetError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return SimulationResetRead(**result.__dict__)
