"""Settings endpoints."""
from fastapi import APIRouter
from datetime import datetime, timezone
from shared import db, invalidate_stats_cache

router = APIRouter()


@router.get("/settings/retention")
async def get_retention_setting():
    setting = await db.app_settings.find_one({"key": "retention_days"}, {"_id": 0})
    return {"retention_days": setting.get("value", 30) if setting else 30}


@router.put("/settings/retention")
async def set_retention_setting(body: dict):
    days = body.get("retention_days", 30)
    if not isinstance(days, int) or days < 1 or days > 365:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="retention_days must be 1-365")
    await db.app_settings.update_one(
        {"key": "retention_days"},
        {"$set": {"key": "retention_days", "value": days, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    invalidate_stats_cache()
    return {"retention_days": days, "message": "Retention window updated"}
