from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.core.deps import get_current_user, require_role
from app.core.security import hash_password
from app.database.session import get_db
from app.users.models import RoleName, User
from app.users.repository import UserRepository
from app.users.schemas import (
    UserCreate,
    UserRead,
    UserResetPassword,
    UserUpdateRole,
    UserUpdateStatus,
)

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _to_read(user: User) -> UserRead:
    return UserRead(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role.name,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.get("", response_model=list[UserRead], dependencies=[Depends(require_role(RoleName.ADMIN))])
def list_users(db: Session = Depends(get_db)) -> list[UserRead]:
    return [_to_read(u) for u in UserRepository(db).list_all()]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
) -> UserRead:
    repo = UserRepository(db)

    if repo.get_by_username(payload.username) or repo.get_by_email(payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already exists.")

    role = repo.get_role_by_name(payload.role)
    if role is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown role.")

    user = repo.create(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role_id=role.id,
    )

    AuditService(db).record(
        action="user.create",
        actor=current_user,
        target_type="user",
        target_id=user.id,
        detail=f"Created user '{user.username}' with role {role.name.value}",
        ip_address=request.client.host,
    )

    return _to_read(user)


@router.get("/me", response_model=UserRead)
def get_my_profile(current_user: User = Depends(get_current_user)) -> UserRead:
    return _to_read(current_user)


@router.patch("/{user_id}/role", response_model=UserRead)
def update_role(
    user_id: str,
    payload: UserUpdateRole,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
) -> UserRead:
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    role = repo.get_role_by_name(payload.role)
    if role is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown role.")

    if (
        user.role.name == RoleName.ADMIN
        and role.name != RoleName.ADMIN
        and repo.count_active_admins(exclude_user_id=user.id) == 0
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot change the role of the last active admin.",
        )

    previous_role = user.role.name.value
    updated = repo.update_role(user, role)

    AuditService(db).record(
        action="user.role_change",
        actor=current_user,
        target_type="user",
        target_id=user.id,
        detail=f"Role changed from {previous_role} to {role.name.value}",
        ip_address=request.client.host,
    )

    return _to_read(updated)


@router.patch("/{user_id}/status", response_model=UserRead)
def update_status(
    user_id: str,
    payload: UserUpdateStatus,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
) -> UserRead:
    """Activate or deactivate a user account.

    Deactivation is preferred over deletion for accounts with history:
    it immediately blocks login (see auth flow) without breaking
    foreign keys from audit logs, incidents, alerts, etc.
    """
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if str(user.id) == str(current_user.id) and not payload.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account.")

    if (
        user.role.name == RoleName.ADMIN
        and not payload.is_active
        and repo.count_active_admins(exclude_user_id=user.id) == 0
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot deactivate the last active admin.",
        )

    if user.is_active == payload.is_active:
        return _to_read(user)

    updated = repo.set_active(user, payload.is_active)

    AuditService(db).record(
        action="user.activate" if payload.is_active else "user.deactivate",
        actor=current_user,
        target_type="user",
        target_id=user.id,
        detail=f"User '{user.username}' {'activated' if payload.is_active else 'deactivated'}",
        ip_address=request.client.host,
    )

    return _to_read(updated)


@router.post("/{user_id}/reset-password", response_model=UserRead)
def reset_password(
    user_id: str,
    payload: UserResetPassword,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
) -> UserRead:
    """Admin-initiated password reset.

    Sets a new password directly (no email flow — this is an internal
    tool). The user is not otherwise notified by the API; tell them
    the new password out of band.
    """
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    updated = repo.set_password(user, hash_password(payload.new_password))

    AuditService(db).record(
        action="user.password_reset",
        actor=current_user,
        target_type="user",
        target_id=user.id,
        detail=f"Password reset for user '{user.username}' by admin",
        ip_address=request.client.host,
    )

    return _to_read(updated)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
) -> None:
    """Permanently delete a user.

    Fails with 409 if the account has related records (audit log
    entries, assigned incidents, discovery scans, etc.) that reference
    it by foreign key — deactivating (PATCH .../status) is the correct
    action for any account with real history, since deleting it would
    either be rejected by the database or, on backends that don't
    enforce the constraint, silently orphan those records.
    """
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if str(user.id) == str(current_user.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account.")

    if (
        user.role.name == RoleName.ADMIN
        and repo.count_active_admins(exclude_user_id=user.id) == 0
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete the last active admin.",
        )

    username = user.username
    try:
        repo.delete(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This user has related records (audit history, assigned "
                "incidents, discovery scans, etc.) and cannot be deleted. "
                "Deactivate the account instead."
            ),
        )

    AuditService(db).record(
        action="user.delete",
        actor=current_user,
        target_type="user",
        target_id=user_id,
        detail=f"Deleted user '{username}'",
        ip_address=request.client.host,
    )