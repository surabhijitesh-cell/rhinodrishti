"""Notification REST endpoints — preferences, subscriptions, inbox."""
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from shared import db
from utils.auth import get_current_user

router = APIRouter()

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class PushSubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    platform: Optional[str] = "unknown"
    user_agent: Optional[str] = ""


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


class NotificationPrefsUpdate(BaseModel):
    enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    min_priority_score: Optional[int] = None
    notify_faultline_escalations: Optional[bool] = None
    notify_paoi_impact: Optional[bool] = None
    notify_flagged_news: Optional[bool] = None
    notify_state_escalations: Optional[bool] = None
    notify_high_priority: Optional[bool] = None
    notify_user_filter_match: Optional[bool] = None
    regions: Optional[List[str]] = None          # regions of interest for filtering
    actors: Optional[List[str]] = None
    faultline_ids: Optional[List[str]] = None
    signal_buckets: Optional[List[str]] = None


# ── VAPID public key ──────────────────────────────────────────────────────────

@router.get("/notifications/vapid-public-key")
async def get_vapid_public_key():
    return {"public_key": VAPID_PUBLIC_KEY}


# ── Push subscription lifecycle ───────────────────────────────────────────────

@router.post("/notifications/subscribe")
async def subscribe_push(
    data: PushSubscribeRequest,
    user: dict = Depends(get_current_user),
):
    now = datetime.now(timezone.utc).isoformat()
    await db.push_subscriptions.update_one(
        {"endpoint": data.endpoint},
        {"$set": {
            "user_id": user["id"],
            "endpoint": data.endpoint,
            "p256dh": data.p256dh,
            "auth": data.auth,
            "platform": data.platform,
            "user_agent": data.user_agent,
            "active": True,
            "consecutive_failures": 0,
            "failure_reason": None,
            "last_failure_at": None,
            "updated_at": now,
        }, "$setOnInsert": {
            "id": str(uuid.uuid4()),
            "created_at": now,
            "last_success_at": None,
        }},
        upsert=True,
    )
    return {"status": "subscribed"}


@router.delete("/notifications/unsubscribe")
async def unsubscribe_push(
    data: PushUnsubscribeRequest,
    user: dict = Depends(get_current_user),
):
    await db.push_subscriptions.update_one(
        {"endpoint": data.endpoint, "user_id": user["id"]},
        {"$set": {"active": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"status": "unsubscribed"}


# ── Notification preferences ──────────────────────────────────────────────────

@router.get("/notifications/preferences")
async def get_preferences(user: dict = Depends(get_current_user)):
    prefs = await db.user_notification_prefs.find_one(
        {"user_id": user["id"]}, {"_id": 0}
    )
    if not prefs:
        # Return defaults — not yet persisted
        prefs = _default_prefs(user["id"])
    return prefs


@router.put("/notifications/preferences")
async def update_preferences(
    data: NotificationPrefsUpdate,
    user: dict = Depends(get_current_user),
):
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.user_notification_prefs.update_one(
        {"user_id": user["id"]},
        {"$set": update, "$setOnInsert": {
            "user_id": user["id"],
            **_default_prefs(user["id"]),
        }},
        upsert=True,
    )
    prefs = await db.user_notification_prefs.find_one(
        {"user_id": user["id"]}, {"_id": 0}
    )
    return prefs


# ── Notification inbox ────────────────────────────────────────────────────────

@router.get("/notifications/unread-count")
async def get_unread_count(user: dict = Depends(get_current_user)):
    count = await db.notification_recipients.count_documents(
        {"user_id": user["id"], "is_read": False}
    )
    return {"count": count}


@router.get("/notifications")
async def list_notifications(
    page: int = 1,
    limit: int = 20,
    unread_only: bool = False,
    user: dict = Depends(get_current_user),
):
    query: dict = {"user_id": user["id"]}
    if unread_only:
        query["is_read"] = False

    skip = (page - 1) * limit
    total = await db.notification_recipients.count_documents(query)
    recs = await db.notification_recipients.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(None)

    # Enrich with notification body
    notif_ids = [r["notification_id"] for r in recs]
    notifs_raw = await db.notifications.find(
        {"id": {"$in": notif_ids}}, {"_id": 0}
    ).to_list(None)
    notifs_by_id = {n["id"]: n for n in notifs_raw}

    results = []
    for rec in recs:
        n = notifs_by_id.get(rec["notification_id"], {})
        results.append({
            "notification_id": rec["notification_id"],
            "recipient_id": rec["id"],
            "type": n.get("type", ""),
            "title": n.get("title", ""),
            "body": n.get("body", ""),
            "deep_link": n.get("deep_link", "/"),
            "payload_json": n.get("payload_json", {}),
            "is_read": rec.get("is_read", False),
            "read_at": rec.get("read_at"),
            "created_at": rec.get("created_at"),
        })

    return {"notifications": results, "total": total, "page": page}


@router.post("/notifications/seen")
async def mark_seen(user: dict = Depends(get_current_user)):
    """Mark all unread notifications as seen (viewed in panel but not clicked)."""
    now = datetime.now(timezone.utc).isoformat()
    await db.notification_recipients.update_many(
        {"user_id": user["id"], "seen_at": None},
        {"$set": {"seen_at": now}}
    )
    return {"status": "ok"}


@router.post("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user: dict = Depends(get_current_user),
):
    now = datetime.now(timezone.utc).isoformat()
    result = await db.notification_recipients.update_one(
        {"notification_id": notification_id, "user_id": user["id"], "is_read": False},
        {"$set": {"is_read": True, "read_at": now}}
    )
    return {"updated": result.modified_count}


@router.post("/notifications/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc).isoformat()
    result = await db.notification_recipients.update_many(
        {"user_id": user["id"], "is_read": False},
        {"$set": {"is_read": True, "read_at": now}}
    )
    return {"updated": result.modified_count}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_prefs(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "enabled": True,
        "in_app_enabled": True,
        "push_enabled": False,
        "min_priority_score": 90,
        "notify_faultline_escalations": True,
        "notify_paoi_impact": True,
        "notify_flagged_news": True,
        "notify_state_escalations": True,
        "notify_high_priority": True,
        "notify_user_filter_match": True,
        "regions": [],          # empty = all regions; populated = only these states
        "actors": [],           # empty = all actors; populated = only these actor names
        "faultline_ids": [],    # empty = all faultlines
        "signal_buckets": [],   # empty = all buckets
        "updated_at": None,
    }
