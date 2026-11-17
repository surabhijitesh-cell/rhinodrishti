"""Authentication utilities — JWT tokens and password hashing."""
import os
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

JWT_SECRET = os.environ.get("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "1440"))


class LoginLimiter:
    """In-memory failed-login counter (single server instance).
    shortcut: resets on restart and is not shared across instances; use Redis if scaled out."""

    def __init__(self, max_fails: int = 5, window_s: int = 900, max_keys: int = 5000):
        self.max_fails, self.window_s, self.max_keys = max_fails, window_s, max_keys
        self._fails: dict = {}  # key -> list of failure timestamps

    def _recent(self, key: str, now: float) -> list:
        recent = [t for t in self._fails.get(key, []) if now - t < self.window_s]
        if recent:
            self._fails[key] = recent
        else:
            self._fails.pop(key, None)
        return recent

    def retry_after(self, key: str, now: float) -> int:
        """Seconds until allowed again; 0 if not locked."""
        recent = self._recent(key, now)
        if len(recent) < self.max_fails:
            return 0
        return max(1, int(recent[0] + self.window_s - now))

    def record_failure(self, key: str, now: float) -> None:
        recent = self._recent(key, now)
        recent.append(now)
        self._fails.pop(key, None)
        self._fails[key] = recent  # re-insert = newest at end
        while len(self._fails) > self.max_keys:
            self._fails.pop(next(iter(self._fails)))

    def clear(self, key: str) -> None:
        self._fails.pop(key, None)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def token_version_ok(payload: dict, user: dict) -> bool:
    """A token is valid only if its `tv` claim matches the user's current
    token_version (both default to 0, so older tokens keep working)."""
    return payload.get("tv", 0) == user.get("token_version", 0)


def create_access_token(data: dict, token_version: int = 0) -> str:
    to_encode = data.copy()
    to_encode["tv"] = token_version
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    from shared import db
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account deactivated")
    if not token_version_ok(payload, user):
        raise HTTPException(status_code=401, detail="Session ended, please log in again")

    # IOD: the user document's own `iod` field wins when present (admin-set
    # via User Management). Falls back to the static username->IOD registry,
    # then to IOD-1. See iod_registry.py.
    if not user.get("iod"):
        from iod_registry import resolve_user_iod
        user["iod"] = resolve_user_iod(user["username"])

    # Refresh this login session's "last active" timestamp — backs the
    # Currently Online view and session-duration figures in the Activity
    # report. Never blocks/fails the actual request. See user_activity.py.
    session_id = payload.get("session_id")
    if session_id:
        from user_activity import touch_session
        await touch_session(session_id)

    return user


async def get_current_session_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[str]:
    """Decode the bearer token and return its session_id, or None. Used only
    by /auth/logout to mark the session's precise end time."""
    if not credentials:
        return None
    try:
        payload = verify_token(credentials.credentials)
    except HTTPException:
        return None
    return payload.get("session_id")


async def get_current_token_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[str]:
    """User id from a still-valid bearer token, or None. Used by /auth/logout."""
    if not credentials:
        return None
    try:
        return verify_token(credentials.credentials).get("sub")
    except HTTPException:
        return None


async def require_admin_role(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_admin_for_changes(request: Request, user: dict = Depends(get_current_user)):
    """Any logged-in user may read; only admins may change. For routers whose
    screens are admin-only but whose read endpoints other screens also use."""
    if request.method not in ("GET", "HEAD") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def get_current_user_optional(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Same as get_current_user but never raises — returns None for missing,
    invalid, or expired tokens. For endpoints that work unauthenticated (e.g.
    the public intelligence feed) but personalize when a valid session exists
    (IOD-based ranking boost)."""
    if not credentials:
        return None
    try:
        payload = verify_token(credentials.credentials)
    except HTTPException:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None

    from shared import db
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user or not user.get("is_active", True) or not token_version_ok(payload, user):
        return None

    if not user.get("iod"):
        from iod_registry import resolve_user_iod
        user["iod"] = resolve_user_iod(user["username"])
    return user
