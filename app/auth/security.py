import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from app.auth.models import UserContext
from app.core.config import settings
from app.core.errors import CopilotError

from app.auth.database import get_user, pwd_context
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

# Dummy local DB for auth - DEPRECATED, use database.py instead
USERS = {
    "admin": {"password_hash": pwd_context.hash("admin123"), "role": "admin"},
    "user": {"password_hash": pwd_context.hash("user123"), "role": "user"}
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def resolve_user(token: str | None = Depends(oauth2_scheme)) -> UserContext:
    """Resolve user from JWT. Returns guest only when auth is disabled."""
    if not settings.AUTH_ENABLED:
        return UserContext(role="admin", user_id="local-dev")
    if not token:
        raise CopilotError("Authentication required. Please provide a valid token.", status_code=401)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str | None = payload.get("sub")
        role: str | None = payload.get("role")
        if username is None or role is None:
            raise CopilotError("Invalid token payload.", status_code=401)
        return UserContext(role=role, user_id=username)
    except jwt.ExpiredSignatureError:
        raise CopilotError("Token has expired. Please log in again.", status_code=401)
    except jwt.PyJWTError:
        raise CopilotError("Invalid authentication token.", status_code=401)


def resolve_user_optional(token: str | None = Depends(oauth2_scheme)) -> UserContext:
    """Resolve user from JWT. Returns guest if no token provided (for public endpoints)."""
    if not settings.AUTH_ENABLED:
        return UserContext(role="admin", user_id="local-dev")
    if not token:
        return UserContext(role="guest", user_id="guest")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        role = payload.get("role")
        if username and role:
            return UserContext(role=role, user_id=username)
    except jwt.PyJWTError:
        pass
    return UserContext(role="guest", user_id="guest")


def require_admin(user: UserContext = Depends(resolve_user)) -> None:
    if user.role != "admin":
        raise CopilotError("Admin role required.", status_code=403)
