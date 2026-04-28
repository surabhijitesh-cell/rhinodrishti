"""Settings endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
from shared import db, invalidate_stats_cache, logger
from feedback_bias import invalidate_bias_cache
from utils.auth import require_admin_role

router = APIRouter()

VALID_CATEGORIES = ["regional", "national", "bangladesh", "myanmar", "international", "government"]
VALID_PRIORITIES = ["grassroots", "standard", "elite"]


# ============================================================
# RSS Feed Management (Admin only)
# ============================================================

class AddFeedRequest(BaseModel):
    name: str
    url: str
    category: str = "national"
    language: str = "en"
    region: str = "India"
    priority: str = "standard"


@router.get("/settings/rss-feeds")
async def get_rss_feeds(user: dict = Depends(require_admin_role)):
    """Return all RSS sources — hardcoded + custom user-added feeds."""
    from rss_fetcher import RSS_SOURCES

    # Get custom feeds from DB
    custom_feeds = await db.custom_rss_feeds.find({}, {"_id": 0}).sort("added_at", -1).to_list(200)

    return {
        "builtin_count": len(RSS_SOURCES),
        "custom_count": len(custom_feeds),
        "total": len(RSS_SOURCES) + len(custom_feeds),
        "custom_feeds": custom_feeds,
    }


@router.post("/settings/rss-feeds")
async def add_custom_feed(body: AddFeedRequest, user: dict = Depends(require_admin_role)):
    """Add a new custom RSS feed."""
    name = body.name.strip()
    url = body.url.strip()

    if not name or len(name) < 2:
        raise HTTPException(status_code=400, detail="Feed name is required (min 2 chars)")
    if not url or not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Valid RSS feed URL is required")
    if body.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Category must be one of: {VALID_CATEGORIES}")
    if body.priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Priority must be one of: {VALID_PRIORITIES}")

    # Check for duplicate URL across builtin + custom
    from rss_fetcher import RSS_SOURCES
    builtin_urls = {s["url"] for s in RSS_SOURCES}
    if url in builtin_urls:
        raise HTTPException(status_code=409, detail="This URL already exists in the built-in feed list")

    existing = await db.custom_rss_feeds.find_one({"url": url}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="This URL already exists in custom feeds")

    doc = {
        "name": name,
        "url": url,
        "category": body.category,
        "language": body.language.strip() or "en",
        "region": body.region.strip() or "India",
        "priority": body.priority,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "added_by": user.get("username", "admin"),
        "active": True,
    }
    await db.custom_rss_feeds.insert_one(doc)
    logger.info(f"Custom RSS feed added: '{name}' ({url}) by {user.get('username')}")
    return {"message": f"Feed '{name}' added", "feed": {k: v for k, v in doc.items() if k != "_id"}}


@router.delete("/settings/rss-feeds")
async def delete_custom_feed(url: str, user: dict = Depends(require_admin_role)):
    """Remove a custom RSS feed."""
    result = await db.custom_rss_feeds.delete_one({"url": url})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Feed not found")
    logger.info(f"Custom RSS feed deleted: {url} by {user.get('username')}")
    return {"message": "Feed removed"}


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


# ============================================================
# Local Database Setup — status + migration log
# ============================================================

@router.get("/settings/local-db-status")
async def get_local_db_status():
    """
    Returns whether the backend is connected to a local (Tailscale) MongoDB
    or still using MongoDB Atlas, plus any migration log entries.
    """
    import os
    mongo_url = os.environ.get("MONGO_URL", "")
    tailscale_key = os.environ.get("TAILSCALE_AUTH_KEY", "")

    # Detect mode from MONGO_URL
    if "mongodb+srv://" in mongo_url or "atlas" in mongo_url.lower():
        mode = "atlas"
    elif tailscale_key:
        mode = "local_tailscale"
    else:
        mode = "local_direct"

    # Migration log (written by migrate_atlas_to_local.py)
    log_entries = await db["_migration_log"].find(
        {}, {"_id": 0}
    ).sort("migrated_at", -1).limit(5).to_list(5)

    # DB stats
    try:
        stats = await db.command("dbStats")
        data_size_mb = round(stats.get("dataSize", 0) / 1024 / 1024, 1)
        storage_mb   = round(stats.get("storageSize", 0) / 1024 / 1024, 1)
        collections  = stats.get("collections", 0)
    except Exception:
        data_size_mb = storage_mb = collections = None

    return {
        "mode":            mode,           # "atlas" | "local_tailscale" | "local_direct"
        "mongo_url_hint":  mongo_url[:30] + "..." if mongo_url else "",
        "tailscale_ready": bool(tailscale_key),
        "data_size_mb":    data_size_mb,
        "storage_mb":      storage_mb,
        "collections":     collections,
        "migration_log":   log_entries,
    }
