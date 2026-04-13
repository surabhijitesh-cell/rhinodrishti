"""Settings endpoints."""
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from shared import db, invalidate_stats_cache
from feedback_bias import invalidate_bias_cache

router = APIRouter()


@router.get("/settings/retention")
async def get_retention_setting():
    settings = await db.app_settings.find_one({"key": "retention_days"}, {"_id": 0})
    return {"retention_days": settings.get("value", 30) if settings else 30}


@router.put("/settings/retention")
async def set_retention_setting(body: dict):
    days = body.get("retention_days", 30)
    if not isinstance(days, int) or days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="retention_days must be integer 1-365")
    await db.app_settings.update_one(
        {"key": "retention_days"},
        {"$set": {"key": "retention_days", "value": days, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    invalidate_stats_cache()
    return {"message": f"Retention window set to {days} days", "retention_days": days}


@router.get("/settings/feedback")
async def get_feedback_settings():
    settings = await db.app_settings.find_one({"key": "max_feedback_per_item"}, {"_id": 0})
    return {"max_feedback_per_item": settings.get("value", 20) if settings else 20}


@router.put("/settings/feedback")
async def set_feedback_settings(body: dict):
    max_val = body.get("max_feedback_per_item", 20)
    if not isinstance(max_val, int) or max_val < 1 or max_val > 500:
        raise HTTPException(status_code=400, detail="max_feedback_per_item must be integer 1-500")
    await db.app_settings.update_one(
        {"key": "max_feedback_per_item"},
        {"$set": {"key": "max_feedback_per_item", "value": max_val, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    return {"message": f"Max feedback per item set to {max_val}", "max_feedback_per_item": max_val}


# ============================================================
# Feedback Bias Configuration
# ============================================================
VALID_WINDOWS = ["rolling_30", "all_time"]
VALID_INFLUENCES = ["light", "moderate", "high"]


@router.get("/settings/bias")
async def get_bias_settings():
    window_doc = await db.app_settings.find_one({"key": "bias_window"}, {"_id": 0})
    influence_doc = await db.app_settings.find_one({"key": "bias_influence"}, {"_id": 0})
    return {
        "bias_window": window_doc.get("value", "rolling_30") if window_doc else "rolling_30",
        "bias_influence": influence_doc.get("value", "moderate") if influence_doc else "moderate",
    }


@router.put("/settings/bias")
async def set_bias_settings(body: dict):
    window = body.get("bias_window")
    influence = body.get("bias_influence")

    if window and window not in VALID_WINDOWS:
        raise HTTPException(status_code=400, detail=f"bias_window must be one of {VALID_WINDOWS}")
    if influence and influence not in VALID_INFLUENCES:
        raise HTTPException(status_code=400, detail=f"bias_influence must be one of {VALID_INFLUENCES}")

    now = datetime.now(timezone.utc).isoformat()
    if window:
        await db.app_settings.update_one(
            {"key": "bias_window"},
            {"$set": {"key": "bias_window", "value": window, "updated_at": now}},
            upsert=True
        )
    if influence:
        await db.app_settings.update_one(
            {"key": "bias_influence"},
            {"$set": {"key": "bias_influence", "value": influence, "updated_at": now}},
            upsert=True
        )

    # Invalidate bias cache so next classification uses new settings
    invalidate_bias_cache()

    parts = []
    if window:
        parts.append(f"window={window}")
    if influence:
        parts.append(f"influence={influence}")
    return {
        "message": f"Bias settings updated: {', '.join(parts)}",
        "bias_window": window,
        "bias_influence": influence,
    }
