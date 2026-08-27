from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.health.service import HealthService

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/")
async def health_check(db: Session = Depends(get_db)):
    """Basic health check."""
    service = HealthService(db)
    return service.check_health()


@router.get("/liveness")
async def liveness():
    """Kubernetes liveness probe."""
    return {"status": "alive"}


@router.get("/readiness")
async def readiness(db: Session = Depends(get_db)):
    """Kubernetes readiness probe."""
    service = HealthService(db)
    return service.check_health()