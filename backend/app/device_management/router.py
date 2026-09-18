from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import require_any_role, require_role
from app.database.session import get_db
from app.device_management.models import DeviceTask, ManagedDevice
from app.device_management.schemas import (
    DeviceTaskCreate,
    DeviceTaskRead,
    EnrollmentIssued,
    ManagedDeviceRead,
)
from app.device_management.service import DeviceManagementError, DeviceManagementService, PolicyError
from app.users.models import RoleName, User

router = APIRouter(prefix="/api/v1/device-management", tags=["device-management"])


@router.get("/devices", response_model=list[ManagedDeviceRead])
def list_devices(db: Session = Depends(get_db), _: User = Depends(require_any_role)) -> list[ManagedDeviceRead]:
    return db.query(ManagedDevice).order_by(ManagedDevice.created_at.desc()).all()


@router.post("/devices/{asset_id}/enroll", response_model=EnrollmentIssued)
def enroll_device(
    asset_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
) -> EnrollmentIssued:
    try:
        device, token = DeviceManagementService(db).enroll_device(asset_id, current_user, request.client.host)
    except DeviceManagementError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return EnrollmentIssued(device=device, enrollment_token=token, expires_at=device.enrollment_token_expires_at)


@router.post("/devices/{managed_device_id}/revoke", response_model=ManagedDeviceRead)
def revoke_device(
    managed_device_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
) -> ManagedDeviceRead:
    try:
        return DeviceManagementService(db).revoke_device(managed_device_id, current_user, request.client.host)
    except DeviceManagementError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/devices/{managed_device_id}/tasks", response_model=list[DeviceTaskRead])
def list_tasks(
    managed_device_id: str, db: Session = Depends(get_db), _: User = Depends(require_any_role)
) -> list[DeviceTaskRead]:
    return (
        db.query(DeviceTask)
        .filter_by(managed_device_id=managed_device_id)
        .order_by(DeviceTask.created_at.desc())
        .all()
    )


@router.post("/devices/{managed_device_id}/tasks", response_model=DeviceTaskRead)
def queue_task(
    managed_device_id: str,
    payload: DeviceTaskCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
) -> DeviceTaskRead:
    try:
        return DeviceManagementService(db).queue_task(
            managed_device_id,
            payload.action_type,
            payload.params,
            current_user,
            payload.confirm,
            request.client.host,
        )
    except PolicyError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except DeviceManagementError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
