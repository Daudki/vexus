from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_any_role
from app.database.session import get_db
from app.correlation.schemas import CorrelationCandidateRead
from app.correlation.service import CorrelationService
from app.users.models import User

router = APIRouter(prefix="/api/v1/correlation", tags=["correlation"])


@router.get("/candidates", response_model=list[CorrelationCandidateRead])
def list_candidates(
    window_seconds: int = Query(default=900, ge=1, le=86400),
    db: Session = Depends(get_db),
    _: User = Depends(require_any_role),
) -> list[CorrelationCandidateRead]:
    return CorrelationService(db).find_candidates(window_seconds=window_seconds)
