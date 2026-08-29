from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app.database.session import get_db
from app.core.deps import get_current_user, require_role
from app.users.models import User, RoleName, Role
from app.users.repository import UserRepository
from app.audit.service import AuditService
from app.audit.models import AuditLog
from app.core.security import hash_password
from app.admin.schemas import (
    UserCreate, UserUpdate, UserResponse,
    RoleCreate, RoleUpdate, RoleResponse,
    SystemSettings, SettingsUpdate,
    SystemStats, AuditLogResponse,
    ScanRangesUpdate, ScanRangesResponse
)
from app.config.settings import get_settings

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


# ==================== Users ====================

@router.get("/users", response_model=dict)
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
):
    """List all users (admin only)."""
    repo = UserRepository(db)
    users = repo.list_all()
    
    # Filter inactive if not included
    if not include_inactive:
        users = [u for u in users if u.is_active]
    
    # Paginate
    total = len(users)
    users = users[skip:skip + limit]
    
    return {
        "items": [_user_to_response(u) for u in users],
        "total": total,
    }


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
):
    """Get a specific user (admin only)."""
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _user_to_response(user)


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
):
    """Create a new user (admin only)."""
    repo = UserRepository(db)
    
    # Check if username exists
    if repo.get_by_username(data.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    
    # Check if email exists
    if repo.get_by_email(data.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    
    # Get role
    role = repo.get_role_by_name(data.role)
    if not role:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    
    # Create user
    user = repo.create(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role_id=role.id,
    )
    
    # Audit
    AuditService(db).record(
        action="admin.create_user",
        actor=current_user,
        target_type="user",
        target_id=str(user.id),
        detail=f"Created user {user.username} with role {data.role.value}",
    )
    
    db.commit()
    return _user_to_response(user)


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
):
    """Update a user (admin only)."""
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Update fields
    if data.email:
        user.email = data.email
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.password:
        user.password_hash = hash_password(data.password)
    if data.role:
        role = repo.get_role_by_name(data.role)
        if not role:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
        user.role_id = role.id
    
    db.flush()
    
    # Audit
    AuditService(db).record(
        action="admin.update_user",
        actor=current_user,
        target_type="user",
        target_id=str(user.id),
        detail=f"Updated user {user.username}",
    )
    
    db.commit()
    return _user_to_response(user)


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
):
    """Delete a user (admin only)."""
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Prevent deleting yourself
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")
    
    # Audit before deletion
    AuditService(db).record(
        action="admin.delete_user",
        actor=current_user,
        target_type="user",
        target_id=str(user.id),
        detail=f"Deleted user {user.username}",
    )
    
    db.delete(user)
    db.commit()
    return {"message": f"User {user.username} deleted"}


@router.patch("/users/{user_id}/toggle-active")
def toggle_user_active(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
):
    """Toggle user active status (admin only)."""
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Prevent deactivating yourself
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")
    
    user.is_active = not user.is_active
    db.flush()
    
    AuditService(db).record(
        action="admin.toggle_user",
        actor=current_user,
        target_type="user",
        target_id=str(user.id),
        detail=f"User {user.username} {'activated' if user.is_active else 'deactivated'}",
    )
    
    db.commit()
    return {"message": f"User {user.username} {'activated' if user.is_active else 'deactivated'}"}


# ==================== Roles ====================

@router.get("/roles", response_model=List[RoleResponse])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
):
    """List all roles (admin only)."""
    roles = db.query(Role).all()
    return [_role_to_response(r) for r in roles]


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
):
    """Create a new role (admin only)."""
    # Check if role exists
    existing = db.query(Role).filter(Role.name == data.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role already exists")
    
    role = Role(name=data.name, description=data.description)
    db.add(role)
    db.flush()
    
    AuditService(db).record(
        action="admin.create_role",
        actor=current_user,
        target_type="role",
        target_id=str(role.id),
        detail=f"Created role {role.name}",
    )
    
    db.commit()
    return _role_to_response(role)


@router.put("/roles/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: str,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
):
    """Update a role (admin only)."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    
    if data.description is not None:
        role.description = data.description
    
    db.flush()
    
    AuditService(db).record(
        action="admin.update_role",
        actor=current_user,
        target_type="role",
        target_id=str(role.id),
        detail=f"Updated role {role.name}",
    )
    
    db.commit()
    return _role_to_response(role)


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
):
    """Delete a role (admin only)."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    
    # Don't delete built-in roles
    if role.name in [RoleName.ADMIN, RoleName.ANALYST, RoleName.VIEWER]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete built-in roles")
    
    AuditService(db).record(
        action="admin.delete_role",
        actor=current_user,
        target_type="role",
        target_id=str(role.id),
        detail=f"Deleted role {role.name}",
    )
    
    db.delete(role)
    db.commit()
    return {"message": f"Role {role.name} deleted"}


# ==================== Audit Logs ====================

@router.get("/audit", response_model=dict)
def get_audit_logs(
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
):
    """Get audit logs (admin only)."""
    query = db.query(AuditLog)
    
    if action:
        query = query.filter(AuditLog.action == action)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if start_date:
        query = query.filter(AuditLog.timestamp >= start_date)
    if end_date:
        query = query.filter(AuditLog.timestamp <= end_date)
    
    total = query.count()
    logs = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    
    return {
        "items": [_audit_to_response(log) for log in logs],
        "total": total,
    }


# ==================== Scan Range Settings ====================

@router.get("/settings/scan-ranges", response_model=ScanRangesResponse)
def get_scan_ranges(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
):
    """Get the currently authorized discovery scan ranges."""
    settings = get_settings()
    return ScanRangesResponse(ranges=list(settings.authorized_scan_ranges_list))


@router.put("/settings/scan-ranges", response_model=ScanRangesResponse)
def update_scan_ranges(
    payload: ScanRangesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
):
    """Persist the set of CIDR ranges administrators are allowed to scan."""
    ranges = []
    for entry in payload.ranges:
        clean = str(entry).strip()
        if clean:
            ranges.append(clean)

    settings = get_settings()
    settings.AUTHORIZED_SCAN_RANGES = ranges
    AuditService(db).record(
        action="admin.update_scan_ranges",
        actor=current_user,
        target_type="system",
        target_id="scan_ranges",
        detail=f"Updated authorized scan ranges: {', '.join(ranges) if ranges else 'none'}",
    )
    db.commit()
    return ScanRangesResponse(ranges=ranges)


# ==================== System Stats ====================

@router.get("/stats", response_model=SystemStats)
def get_system_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
):
    """Get system statistics (admin only)."""
    # User stats
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    
    # Asset stats (if tables exist)
    total_assets = 0
    active_assets = 0
    try:
        from app.assets.models import Asset
        total_assets = db.query(Asset).count()
        active_assets = db.query(Asset).filter(Asset.status == "active").count()
    except:
        pass
    
    # Alert stats (if tables exist)
    total_alerts = 0
    new_alerts = 0
    try:
        from app.alerts.models import Alert
        total_alerts = db.query(Alert).count()
        new_alerts = db.query(Alert).filter(Alert.status == "new").count()
    except:
        pass
    
    # Incident stats (if tables exist)
    total_incidents = 0
    open_incidents = 0
    try:
        from app.incidents.models import Incident
        total_incidents = db.query(Incident).count()
        open_incidents = db.query(Incident).filter(Incident.status.in_(["new", "investigating"])).count()
    except:
        pass
    
    return SystemStats(
        total_users=total_users,
        active_users=active_users,
        total_assets=total_assets,
        active_assets=active_assets,
        total_alerts=total_alerts,
        new_alerts=new_alerts,
        total_incidents=total_incidents,
        open_incidents=open_incidents,
        health_status="healthy",
    )


# ==================== Helper Functions ====================

def _user_to_response(user: User) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "full_name": getattr(user, "full_name", None),
        "is_active": user.is_active,
        "role": user.role.name.value if user.role else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if getattr(user, "last_login", None) else None,
    }


def _role_to_response(role: Role) -> dict:
    return {
        "id": str(role.id),
        "name": role.name.value if hasattr(role.name, "value") else role.name,
        "description": role.description,
        "created_at": role.created_at.isoformat() if role.created_at else None,
    }


def _audit_to_response(log: AuditLog) -> dict:
    return {
        "id": str(log.id),
        "user_id": str(log.user_id) if log.user_id else None,
        "action": log.action,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "details": log.details,
        "ip_address": log.ip_address,
        "timestamp": log.timestamp.isoformat(),
    }