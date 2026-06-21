"""Authentication and User Management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from models.user import UserCreate, UserLogin, UserUpdate, PasswordReset, UserInDB, UserResponse
from utils.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_admin_role,
)
from shared import db

router = APIRouter()
users_col = db.users


# ============================================================
# Auth Endpoints
# ============================================================

@router.post("/auth/login")
async def login(data: UserLogin):
    user = await users_col.find_one(
        {"$or": [{"username": data.username}, {"email": data.username}]},
        {"_id": 0}
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account deactivated")
    if not verify_password(data.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user["id"], "role": user.get("role", "viewer")})

    try:
        await users_col.update_one(
            {"id": user["id"]},
            {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}}
        )
    except Exception:
        pass  # DB quota full — last_login update non-fatal

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user.get("email", ""),
            "name": user.get("name", ""),
            "role": user.get("role", "viewer"),
        }
    }


@router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user


# ============================================================
# User Management (Admin only)
# ============================================================

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
    users = await users_col.find(
        {}, {"_id": 0, "password_hash": 0}
    ).sort("created_at", -1).to_list(200)
    return {"users": users}


@router.post("/users")
async def create_user(data: UserCreate, admin: dict = Depends(require_admin_role)):
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if data.role not in ("admin", "analyst", "viewer"):
        raise HTTPException(status_code=400, detail="Role must be admin, analyst, or viewer")

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

    result = await users_col.update_one({"id": user_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    updated = await users_col.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    return updated


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin_role)):
    if admin["id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
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
        {"$set": {"password_hash": hash_password(data.new_password)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Password reset successfully"}
