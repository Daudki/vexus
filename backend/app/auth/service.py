"""
Auth application service.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.core.security import create_token, verify_password, decode_token
from app.users.models import User, RoleName
from app.users.repository import UserRepository


class AuthError(Exception):
    pass


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.audit = AuditService(db)

    def authenticate(self, username: str, password: str, ip_address: str = "") -> User:
        user = self.users.get_by_username(username)
        if user is None:
            user = self.users.get_by_email(username)

        if user is None or not verify_password(password, user.password_hash):
            self.audit.record(
                action="login",
                actor=user,
                detail=f"Failed login attempt for username '{username}'",
                ip_address=ip_address,
                success=False,
            )
            raise AuthError("Invalid username or password.")

        if not user.is_active:
            self.audit.record(
                action="login",
                actor=user,
                detail="Login attempt on disabled account",
                ip_address=ip_address,
                success=False,
            )
            raise AuthError("This account is disabled.")

        # Update last login - use the repository method that handles stale data
        self.users.update_last_login(user, datetime.now(timezone.utc))
        self.audit.record(action="login", actor=user, ip_address=ip_address, success=True)
        
        # Refresh the user to get updated data
        self.db.refresh(user)
        return user

    def issue_tokens(self, user: User) -> tuple[str, str]:
        # Get role name, default to "viewer" if role is None
        if user.role is None:
            # Try to reload the user with role
            self.db.refresh(user)
            # If still None, use VIEWER as fallback
            role_name = user.role.name.value if user.role else RoleName.VIEWER.value
        else:
            role_name = user.role.name.value
        
        access = create_token(
            str(user.id), 
            "access", 
            extra_claims={"role": role_name}
        )
        refresh = create_token(str(user.id), "refresh")
        return access, refresh

    def refresh_access_token(self, refresh_token: str) -> str:
        claims = decode_token(refresh_token)
        if claims is None or claims.get("type") != "refresh":
            raise AuthError("Invalid or expired refresh token.")

        user = self.users.get_by_id(claims["sub"])
        if user is None or not user.is_active:
            raise AuthError("User no longer active.")

        role_name = user.role.name.value if user.role else RoleName.VIEWER.value
        
        return create_token(
            str(user.id), 
            "access", 
            extra_claims={"role": role_name}
        )