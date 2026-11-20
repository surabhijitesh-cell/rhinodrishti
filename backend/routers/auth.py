"""Authentication and User Management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone
import time
import secrets
import string
from models.user import UserCreate, UserLogin, UserUpdate, PasswordReset, UserInDB, UserResponse
from utils.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_current_session_id, get_current_token_user_id,
    require_admin_role, LoginLimiter,
)
from shared import db
from user_activity import start_session, end_session

router = APIRouter()
users_col = db.users
login_limiter = LoginLimiter()
# X-Forwarded-For can be faked per request, so also cap guesses per username from any address.
user_limiter = LoginLimiter(max_fails=20)


def _client_ip(request: Request) -> str:
    # Render sits behind a proxy: the real client is the first X-Forwarded-For entry.
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


# ============================================================
# Auth Endpoints
# ============================================================

@router.post("/auth/login")
async def login(data: UserLogin, request: Request):
    ip_address = _client_ip(request)
    user_key = data.username.strip().lower()
    limit_key = f"{user_key}|{ip_address}"
    now = time.time()
    wait = max(login_limiter.retry_after(limit_key, now), user_limiter.retry_after(user_key, now))
    if wait:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Try again in {-(-wait // 60)} minutes.",
        )
    user = await users_col.find_one(
        {"$or": [{"username": data.username}, {"email": data.username}]},
        {"_id": 0}
    )
    if not user:
        login_limiter.record_failure(limit_key, time.time())
        user_limiter.record_failure(user_key, time.time())
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account deactivated")
    if not verify_password(data.password, user.get("password_hash", "")):
        login_limiter.record_failure(limit_key, time.time())
        user_limiter.record_failure(user_key, time.time())
        raise HTTPException(status_code=401, detail="Invalid credentials")

    login_limiter.clear(limit_key)
    user_limiter.clear(user_key)
    session_id = await start_session(user, ip_address)
    token = create_access_token(
        {"sub": user["id"], "role": user.get("role", "viewer"), "session_id": session_id},
        token_version=user.get("token_version", 0),
    )

    try:
        await users_col.update_one(
            {"id": user["id"]},
            {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}}
        )
    except Exception:
        pass  # DB quota full — last_login update non-fatal

    iod = user.get("iod")
    if not iod:
        from iod_registry import resolve_user_iod
        iod = resolve_user_iod(user["username"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user.get("email", ""),
            "name": user.get("name", ""),
            "role": user.get("role", "viewer"),
            "iod": iod,
        }
    }


@router.post("/auth/logout")
async def logout(
    session_id: str = Depends(get_current_session_id),
    user_id: str = Depends(get_current_token_user_id),
):
    """Marks the login session's precise end time — improves the accuracy of
    the Currently Online view and session-duration figures over waiting for
    the away/offline staleness threshold. Best-effort: always returns success
    even for a missing/expired session, since the client clears its token
    regardless."""
    await end_session(session_id)
    if user_id:
        # Bumping the version invalidates every token issued to this user.
        await users_col.update_one({"id": user_id}, {"$inc": {"token_version": 1}})
    return {"message": "Logged out"}


@router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user


# ============================================================
# User Management (Admin only)
# ============================================================

# No look-alike characters (0/O, 1/l/I) so a password can be read out loud.
_PW_LOWER = "abcdefghjkmnpqrstuvwxyz"
_PW_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_PW_DIGITS = "23456789"
_PW_SYMBOLS = "!@#$%"


def generate_password(length: int = 14) -> str:
    """Random password from the operating system's secure generator, always
    containing a lower-case, upper-case, digit and symbol character."""
    length = max(length, 8)
    pools = (_PW_LOWER, _PW_UPPER, _PW_DIGITS, _PW_SYMBOLS)
    chars = [secrets.choice(p) for p in pools]
    chars += [secrets.choice("".join(pools)) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def removes_admin_access(target: dict, updates: dict) -> bool:
    """True if applying `updates` stops an active admin from being an active admin."""
    if target.get("role") != "admin" or target.get("is_active", True) is False:
        return False
    return updates.get("role", "admin") != "admin" or updates.get("is_active", True) is False


async def _other_active_admins(user_id: str) -> int:
    return await users_col.count_documents(
        {"role": "admin", "is_active": {"$ne": False}, "id": {"$ne": user_id}}
    )


@router.post("/users/generate-password")
async def new_generated_password(admin: dict = Depends(require_admin_role)):
    return {"password": generate_password()}

@router.get("/users/active")
async def list_active_users(user: dict = Depends(get_current_user)):
    """Return minimal user info for all active users — used by flag recipient selector."""
    users = await users_col.find(
        {"is_active": True},
        {"_id": 0, "password_hash": 0, "email": 0, "created_at": 0}
    ).sort("username", 1).to_list(500)
    return {"users": users}


@router.get("/users")
async def list_users(admin: dict = Depends(require_admin_role)):
    from iod_registry import resolve_user_iod
    users = await users_col.find(
        {}, {"_id": 0, "password_hash": 0}
    ).sort("created_at", -1).to_list(200)
    for u in users:
        if not u.get("iod"):
            u["iod"] = resolve_user_iod(u["username"])
    return {"users": users}


@router.post("/users")
async def create_user(data: UserCreate, admin: dict = Depends(require_admin_role)):
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if data.role not in ("admin", "analyst", "viewer"):
        raise HTTPException(status_code=400, detail="Role must be admin, analyst, or viewer")
    from iod_registry import ALL_IODS
    if data.iod and data.iod not in ALL_IODS:
        raise HTTPException(status_code=400, detail=f"iod must be one of {ALL_IODS}")

    existing = await users_col.find_one(
        {"$or": [{"username": data.username}, {"email": data.email}]} if data.email else {"username": data.username},
        {"_id": 0}
    )
    if existing:
        raise HTTPException(status_code=409, detail="Username or email already exists")

    user = UserInDB(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
        role=data.role,
        iod=data.iod or "IOD-1",
    )
    doc = user.model_dump()
    await users_col.insert_one(doc)
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    return doc


@router.put("/users/{user_id}")
async def update_user(user_id: str, data: UserUpdate, admin: dict = Depends(require_admin_role)):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "role" in updates and updates["role"] not in ("admin", "analyst", "viewer"):
        raise HTTPException(status_code=400, detail="Role must be admin, analyst, or viewer")
    if "iod" in updates:
        from iod_registry import ALL_IODS
        if updates["iod"] not in ALL_IODS:
            raise HTTPException(status_code=400, detail=f"iod must be one of {ALL_IODS}")

    target = await users_col.find_one({"id": user_id}, {"_id": 0, "role": 1, "is_active": 1})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if removes_admin_access(target, updates) and await _other_active_admins(user_id) == 0:
        raise HTTPException(status_code=400, detail="This is the last active admin. Make another user an active admin first.")

    change = {"$set": updates}
    # A new role (or deactivation) ends the person's current logins so it applies at once.
    if ("role" in updates and updates["role"] != target.get("role")) or updates.get("is_active") is False:
        change["$inc"] = {"token_version": 1}
    result = await users_col.update_one({"id": user_id}, change)
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    updated = await users_col.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    return updated


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin_role)):
    if admin["id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    target = await users_col.find_one({"id": user_id}, {"_id": 0, "role": 1, "is_active": 1})
    if target and removes_admin_access(target, {"is_active": False}) and await _other_active_admins(user_id) == 0:
        raise HTTPException(status_code=400, detail="This is the last active admin and cannot be deleted.")
    result = await users_col.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted"}


@router.put("/users/{user_id}/password")
async def reset_password(user_id: str, data: PasswordReset, admin: dict = Depends(require_admin_role)):
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    result = await users_col.update_one(
        {"id": user_id},
        {"$set": {"password_hash": hash_password(data.new_password)}, "$inc": {"token_version": 1}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Password reset successfully"}
