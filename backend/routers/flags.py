"""Article flagging endpoints — user-to-user flag with notification dispatch."""
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from shared import db
from utils.auth import get_current_user

router = APIRouter()

_FLAG_RATE_LIMIT = 20        # max flags per user per hour
_FLAG_DEDUP_MINUTES = 15     # suppress duplicate flag (same sender+article+recipients) within this window
_FLAG_MAX_RECIPIENTS = 10    # cap recipients per flag action


# ── Schemas ───────────────────────────────────────────────────────────────────

class FlagCreateRequest(BaseModel):
    article_id: str
    article_title: str
    flagged_for_user_ids: List[str]
    message: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/flags")
async def create_flag(
    data: FlagCreateRequest,
    user: dict = Depends(get_current_user),
):
    if user.get("role") not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="Only analysts and admins can flag articles")

    if not data.flagged_for_user_ids:
        raise HTTPException(status_code=400, detail="flagged_for_user_ids must not be empty")

    if len(data.flagged_for_user_ids) > _FLAG_MAX_RECIPIENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot flag for more than {_FLAG_MAX_RECIPIENTS} users at once",
        )

    # Self-flag prevention
    if user["id"] in data.flagged_for_user_ids:
        raise HTTPException(status_code=400, detail="Cannot flag an article for yourself")

    # Validate all recipients exist and are active
    valid_users = await db.users.find(
        {"id": {"$in": data.flagged_for_user_ids}, "is_active": True},
        {"id": 1, "_id": 0},
    ).to_list(None)
    valid_ids = {u["id"] for u in valid_users}
    invalid = [uid for uid in data.flagged_for_user_ids if uid not in valid_ids]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown or inactive users: {invalid}")

    # Rate limit: max 20 flags/hour per sender
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    recent_count = await db.news_flags.count_documents({
        "flagged_by": user["id"],
        "created_at": {"$gte": one_hour_ago},
    })
    if recent_count >= _FLAG_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Flag rate limit exceeded. Try again later.")

    # Dedup: same sender + article + same recipient set within 15 min
    dedup_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=_FLAG_DEDUP_MINUTES)).isoformat()
    sorted_recipients = sorted(data.flagged_for_user_ids)
    existing = await db.news_flags.find_one({
        "flagged_by": user["id"],
        "article_id": data.article_id,
        "flagged_for_user_ids": sorted_recipients,
        "created_at": {"$gte": dedup_cutoff},
    })
    if existing:
        raise HTTPException(
            status_code=409,
            detail="You already flagged this article for the same recipients recently",
        )

    now = datetime.now(timezone.utc).isoformat()
    flag_id = str(uuid.uuid4())

    flag_doc = {
        "id": flag_id,
        "article_id": data.article_id,
        "article_title": data.article_title,
        "flagged_by": user["id"],
        "flagged_by_name": user.get("name") or user.get("username", "Unknown"),
        "flagged_for_user_ids": sorted_recipients,
        "message": data.message,
        "created_at": now,
    }

    # Create notification and dispatch to recipients
    try:
        from utils.notifications import create_and_dispatch_notification
        notif_id = await create_and_dispatch_notification(
            notif_type="FLAGGED_NEWS",
            title=f"{flag_doc['flagged_by_name']} flagged an article for you",
            body=f'"{data.article_title[:80]}"' + (f' — {data.message[:60]}' if data.message else ""),
            payload={
                "article_id": data.article_id,
                "article_title": data.article_title,
                "flagged_by_name": flag_doc["flagged_by_name"],
                "note": data.message,
                "flag_id": flag_id,
            },
            deep_link=f"/feed?highlight={data.article_id}",
            source_type="user",
            source_id=user["id"],
            created_by=user["id"],
            recipient_user_ids=sorted_recipients,
        )
        flag_doc["notification_id"] = notif_id
    except Exception as e:
        # Notification failure must not block the flag creation
        flag_doc["notification_id"] = None

    await db.news_flags.insert_one({**flag_doc, "_id": flag_id})

    return {"flag_id": flag_id, "notification_id": flag_doc.get("notification_id")}


@router.get("/flags/sent")
async def get_sent_flags(
    page: int = 1,
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    skip = (page - 1) * limit
    total = await db.news_flags.count_documents({"flagged_by": user["id"]})
    flags = await db.news_flags.find(
        {"flagged_by": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(None)
    return {"flags": flags, "total": total, "page": page}


@router.get("/flags/received")
async def get_received_flags(
    page: int = 1,
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    skip = (page - 1) * limit
    total = await db.news_flags.count_documents({"flagged_for_user_ids": user["id"]})
    flags = await db.news_flags.find(
        {"flagged_for_user_ids": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(None)

    # Enrich with read status from notification_recipients
    notif_ids = [f.get("notification_id") for f in flags if f.get("notification_id")]
    recs = await db.notification_recipients.find(
        {"notification_id": {"$in": notif_ids}, "user_id": user["id"]},
        {"notification_id": 1, "is_read": 1, "_id": 0},
    ).to_list(None)
    read_state = {r["notification_id"]: r.get("is_read", False) for r in recs}

    for flag in flags:
        nid = flag.get("notification_id")
        flag["is_read"] = read_state.get(nid, True) if nid else True
        flag["deep_link"] = f"/feed?highlight={flag['article_id']}"

    return {"flags": flags, "total": total, "page": page}
