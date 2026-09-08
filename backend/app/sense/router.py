from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_any_role
from app.database.session import get_db
from app.monitoring.models import MetricType
from app.sense.service import SenseService
from app.users.models import User

router = APIRouter(prefix="/api/v1/sense", tags=["sense"])


@router.get("/assets/{asset_id}/baseline")
def get_asset_baseline(
    asset_id: str,
    metric_type: MetricType,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_role),
):
    baseline = SenseService(db).compute_baseline(asset_id, metric_type)
    return {
        "asset_id": baseline.asset_id,
        "metric_type": baseline.metric_type.value,
        "sample_count": baseline.sample_count,
        "average_value": baseline.average_value,
        "stddev_value": baseline.stddev_value,
        "min_value": baseline.min_value,
        "max_value": baseline.max_value,
        "is_usable": baseline.is_usable,
        "notes": baseline.notes,
    }


@router.post("/assets/{asset_id}/evaluate")
def evaluate_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_role),
):
    events = SenseService(db).evaluate_asset(asset_id)
    if not events:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No behavioral anomalies detected.")
    return [{
        "id": event.id,
        "event_type": event.event_type,
        "asset_id": event.asset_id,
        "severity": event.severity.value,
        "confidence": event.confidence,
    } for event in events]
