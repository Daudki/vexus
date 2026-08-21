"""
Auth application service.

Orchestrates login/refresh: pulls the user via the repository, verifies
the password via core.security, issues tokens, and writes an audit log
entry for every attempt (success AND failure — failed logins are one of
the explicit audit examples in the architecture doc).
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.core.security import create_token, verify_password
from app.users.models import User
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

        self.users.update_last_login(user, datetime.now(timezone.utc))
        self.audit.record(action="login", actor=user, ip_address=ip_address, success=True)
        return user

    def issue_tokens(self, user: User) -> tuple[str, str]:
        access = create_token(user.id, "access", extra_claims={"role": user.role.name.value})
        refresh = create_token(user.id, "refresh")
        return access, refresh

    def refresh_access_token(self, refresh_token: str) -> str:
        from app.core.security import decode_token

        claims = decode_token(refresh_token)
        if claims is None or claims.get("type") != "refresh":
            raise AuthError("Invalid or expired refresh token.")

        user = self.users.get_by_id(claims["sub"])
        if user is None or not user.is_active:
            raise AuthError("User no longer active.")

        return create_token(user.id, "access", extra_claims={"role": user.role.name.value})
