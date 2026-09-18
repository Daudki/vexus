from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter
from app.database.session import get_db
from app.device_management.agent_auth import get_current_agent
from app.device_management.models import ManagedDevice
from app.device_management.schemas import (
    AgentEnrollRequest,
    AgentEnrollResponse,
    AgentTaskResult,
    DeviceTaskRead,
)
from app.device_management.service import DeviceManagementError, DeviceManagementService

router = APIRouter(prefix="/api/v1/agent", tags=["agent-protocol"])


@router.post("/enroll", response_model=AgentEnrollResponse)
@limiter.limit("10/minute")
def agent_enroll(request: Request, payload: AgentEnrollRequest, db: Session = Depends(get_db)) -> AgentEnrollResponse:
    try:
        device, token = DeviceManagementService(db).complete_enrollment(
            payload.enrollment_token, payload.agent_version, payload.reported_os
        )
    except DeviceManagementError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return AgentEnrollResponse(agent_token=token, device_id=device.id)


@router.get("/tasks/next", response_model=DeviceTaskRead | None)
@limiter.limit("60/minute")
def agent_next_task(
    request: Request, db: Session = Depends(get_db), device: ManagedDevice = Depends(get_current_agent)
) -> DeviceTaskRead | None:
    return DeviceManagementService(db).get_next_task(device)


@router.post("/tasks/{task_id}/result", response_model=DeviceTaskRead)
@limiter.limit("60/minute")
def agent_report_result(
    task_id: str,
    request: Request,
    payload: AgentTaskResult,
    db: Session = Depends(get_db),
    device: ManagedDevice = Depends(get_current_agent),
) -> DeviceTaskRead:
    try:
        return DeviceManagementService(db).report_result(
            device, task_id, payload.success, payload.result, payload.error_message
        )
    except DeviceManagementError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
