"""App Updates — Notification system for version updates.
Supports priority-based updates (major/minor), per-user acknowledgment,
admin CRUD, and smart UX for long-gap users."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid
from shared import db, logger
from utils.auth import get_current_user, require_admin_role

router = APIRouter()


# ============================================================
# Models
# ============================================================
class CreateUpdateRequest(BaseModel):
    version: str
    message: str
    priority: str = "minor"  # "major" or "minor"


# ============================================================
# User-facing endpoints
# ============================================================

@router.get("/app/updates")
async def get_pending_updates(user: dict = Depends(get_current_user)):
    """Return updates the user hasn't seen yet."""
    last_seen = user.get("last_seen_version", "")

    # Build query: all updates created after the user's last seen version
    query = {}
    if last_seen:
        last_seen_doc = await db.app_updates.find_one(
            {"version": last_seen}, {"_id": 0, "created_at": 1}
        )
        if last_seen_doc and last_seen_doc.get("created_at"):
            query = {"created_at": {"$gt": last_seen_doc["created_at"]}}

    updates = await db.app_updates.find(
        query, {"_id": 0}
    ).sort("created_at", 1).to_list(100)

    major_updates = [u for u in updates if u.get("priority") == "major"]
    minor_updates = [u for u in updates if u.get("priority") == "minor"]

    total_major = len(major_updates)

    # Apply Case logic
    if not updates:
        # Case 6: No updates
        return {"notifications": [], "has_more": False, "total_major": 0, "total_pending": 0}

    if total_major > 0:
        # Case 1/2/4: Major updates exist — ignore minor
        if total_major <= 3:
            # Case 1: Show all major
            notifications = [
                {"version": u["version"], "message": u["message"], "priority": u["priority"]}
                for u in major_updates
            ]
            return {
                "notifications": notifications,
                "has_more": False,
                "total_major": total_major,
                "total_pending": len(updates),
            }
        else:
            # Case 2: Long-gap user — show latest 3 major
            latest_3 = major_updates[-3:]
            notifications = [
                {"version": u["version"], "message": u["message"], "priority": u["priority"]}
                for u in latest_3
            ]
            return {
                "notifications": notifications,
                "has_more": True,
                "total_major": total_major,
                "total_pending": len(updates),
            }
    else:
        # Case 3: Only minor updates
        return {
            "notifications": [
                {"version": minor_updates[-1]["version"],
                 "message": "Performance improvements and bug fixes",
                 "priority": "minor"}
            ],
            "has_more": False,
            "total_major": 0,
            "total_pending": len(updates),
        }


@router.post("/app/updates/acknowledge")
async def acknowledge_updates(user: dict = Depends(get_current_user)):
    """Mark user as having seen all current updates."""
    latest = await db.app_updates.find_one(
        {}, {"_id": 0, "version": 1}, sort=[("created_at", -1)]
    )
    if not latest:
        return {"message": "No updates to acknowledge"}

    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"last_seen_version": latest["version"]}}
    )
    return {"message": "Updates acknowledged", "last_seen_version": latest["version"]}


@router.get("/app/updates/all")
async def get_all_updates(user: dict = Depends(get_current_user)):
    """Return full update history for the 'View All Updates' page."""
    updates = await db.app_updates.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return {"updates": updates}


# ============================================================
# Admin endpoints
# ============================================================

@router.post("/admin/create-update")
async def create_update(body: CreateUpdateRequest, user: dict = Depends(require_admin_role)):
    """Create a new app update notification."""
    version = body.version.strip()
    message = body.message.strip()
    priority = body.priority.lower()

    if not version:
        raise HTTPException(status_code=400, detail="Version is required")
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    if priority not in ("major", "minor"):
        raise HTTPException(status_code=400, detail="Priority must be 'major' or 'minor'")

    # Check for duplicate version
    existing = await db.app_updates.find_one({"version": version}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail=f"Version '{version}' already exists")

    doc = {
        "id": str(uuid.uuid4()),
        "version": version,
        "message": message,
        "priority": priority,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("username", "admin"),
    }
    await db.app_updates.insert_one(doc)
    logger.info(f"App update created: v{version} [{priority}] by {user.get('username')}")
    return {"message": f"Update v{version} created", "update": {k: v for k, v in doc.items() if k != "_id"}}


@router.get("/admin/update-logs")
async def get_update_logs(user: dict = Depends(require_admin_role)):
    """Return all update logs for admin dashboard."""
    updates = await db.app_updates.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return {"updates": updates, "total": len(updates)}


@router.post("/admin/trigger-update-preview")
async def preview_update(body: dict, user: dict = Depends(require_admin_role)):
    """Preview what a specific update would look like as a notification."""
    version = (body.get("version") or "").strip()
    if not version:
        raise HTTPException(status_code=400, detail="Version is required")

    update = await db.app_updates.find_one({"version": version}, {"_id": 0})
    if not update:
        raise HTTPException(status_code=404, detail=f"Version '{version}' not found")

    if update["priority"] == "major":
        preview_message = update["message"]
    else:
        preview_message = "Performance improvements and bug fixes"

    return {
        "version": update["version"],
        "message": preview_message,
        "priority": update["priority"],
        "preview": True,
    }
