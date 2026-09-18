from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.device_management.models import ManagedDevice, ManagedDeviceStatus
from app.device_management.tokens import hash_token

agent_security = HTTPBearer(auto_error=False)


def get_current_agent(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(agent_security),
    db: Session = Depends(get_db),
) -> ManagedDevice:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Agent token required.")

    token_hash = hash_token(credentials.credentials)
    device = (
        db.query(ManagedDevice)
        .filter(ManagedDevice.agent_token_hash == token_hash, ManagedDevice.status == ManagedDeviceStatus.ACTIVE)
        .first()
    )
    if device is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked agent token.")

    device.last_checkin_at = datetime.now(timezone.utc)
    db.commit()
    return device
