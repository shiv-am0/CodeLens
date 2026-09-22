import secrets
import time
from dataclasses import dataclass

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


ALGORITHM = "HS256"
SESSION_COOKIE = "codelens_admin_session"


class AdminAuthenticationError(PermissionError):
    pass


@dataclass(frozen=True)
class AdminSession:
    csrf_token: str


class AdminAuthService:
    def __init__(self) -> None:
        # An ephemeral secret is acceptable in development; production config
        # validation requires a stable secret so sessions work across instances.
        self._development_secret = secrets.token_urlsafe(48)

    @property
    def session_secret(self) -> str:
        return settings.admin_session_secret or self._development_secret

    def verify_password(self, supplied_password: str) -> bool:
        if settings.admin_password_hash:
            try:
                return bcrypt.checkpw(
                    supplied_password.encode(), settings.admin_password_hash.encode()
                )
            except ValueError:
                return False

        if settings.is_production or not settings.admin_password:
            return False
        return secrets.compare_digest(supplied_password, settings.admin_password)

    def create_session_token(self) -> str:
        now = int(time.time())
        payload = {
            "sub": "codelens-admin",
            "iat": now,
            "exp": now + settings.admin_session_hours * 3600,
            "csrf": secrets.token_urlsafe(32),
        }
        return jwt.encode(payload, self.session_secret, algorithm=ALGORITHM)

    def read_session(self, token: str | None) -> AdminSession:
        if not token:
            raise AdminAuthenticationError("Admin login required")
        try:
            payload = jwt.decode(token, self.session_secret, algorithms=[ALGORITHM])
        except JWTError as exc:
            raise AdminAuthenticationError("Admin session is invalid or expired") from exc
        if payload.get("sub") != "codelens-admin" or not payload.get("csrf"):
            raise AdminAuthenticationError("Admin session is invalid")
        return AdminSession(csrf_token=payload["csrf"])

    @staticmethod
    def verify_csrf(session: AdminSession, supplied_token: str) -> None:
        if not secrets.compare_digest(session.csrf_token, supplied_token):
            raise AdminAuthenticationError("Invalid form token")


admin_auth = AdminAuthService()
