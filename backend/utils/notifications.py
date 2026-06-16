"""Unified notification creation and dispatch pipeline."""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("notifications")


async def create_and_dispatch_notification(
    notif_type: str,
    title: str,
    body: str,
    payload: dict,
    deep_link: str,
    source_type: str,
    source_id: Optional[str],
    created_by: Optional[str],
    recipient_user_ids: list,
) -> str:
    """
    Core pipeline: insert notification → insert per-recipient records
    → targeted WS delivery → optional push delivery → log attempts.
    Returns the notification id.
    """
    from shared import db, ws_manager
    from utils.push import send_push_to_user

    now = datetime.now(timezone.utc)
    notif_id = str(uuid.uuid4())

    notif_doc = {
        "id": notif_id,
        "type": notif_type,
        "title": title,
        "body": body,
        "payload_json": payload,
        "deep_link": deep_link,
        "source_type": source_type,
        "source_id": source_id,
        "created_by": created_by,
        "created_at": now.isoformat(),
    }
    await db.notifications.insert_one({**notif_doc, "_id": notif_id})

    for user_id in recipient_user_ids:
        prefs = await db.user_notification_prefs.find_one({"user_id": user_id})
        if prefs and not prefs.get("enabled", True):
            continue

        in_app = (prefs is None) or bool(prefs.get("in_app_enabled", True))
        push = bool(prefs and prefs.get("push_enabled", False))

        channels = []
        if in_app:
            channels.append("in_app")
        if push:
            channels.append("push")

        rec_id = str(uuid.uuid4())
        rec_doc = {
            "id": rec_id,
            "notification_id": notif_id,
            "user_id": user_id,
            "delivery_channels": channels,
            "is_read": False,
            "read_at": None,
            "seen_at": None,
            "dismissed_at": None,
            "push_status": "pending" if push else "not_eligible",
            "push_sent_at": None,
            "created_at": now.isoformat(),
        }
        try:
            await db.notification_recipients.insert_one({**rec_doc, "_id": rec_id})
        except Exception:
            # duplicate (notification_id, user_id) — skip
            continue

        # Targeted WS (non-blocking — skip if user offline)
        try:
            await ws_manager.send_to_user(user_id, {
                "type": "notification",
                "notification": {
                    "id": notif_id,
                    "type": notif_type,
                    "title": title,
                    "body": body,
                    "deep_link": deep_link,
                    "payload_json": payload,
                    "is_read": False,
                    "created_at": now.isoformat(),
                },
                "recipient_id": rec_id,
            })
            await _log_attempt(db, notif_id, rec_id, user_id, "websocket", "success")
        except Exception as e:
            await _log_attempt(db, notif_id, rec_id, user_id, "websocket", "failed", str(e)[:200])

        # Optional push delivery
        if push:
            try:
                await send_push_to_user(db, user_id, notif_doc)
                await db.notification_recipients.update_one(
                    {"id": rec_id},
                    {"$set": {"push_status": "sent", "push_sent_at": now.isoformat()}}
                )
                await _log_attempt(db, notif_id, rec_id, user_id, "push", "success")
            except Exception as e:
                await db.notification_recipients.update_one(
                    {"id": rec_id}, {"$set": {"push_status": "failed"}}
                )
                await _log_attempt(db, notif_id, rec_id, user_id, "push", "failed", str(e)[:200])

    return notif_id


async def resolve_system_notification_recipients(db, notif_type: str, item: dict = None) -> list:
    """
    Return list of user_ids that should receive a system-generated notification,
    filtered by their notification preferences.
    """
    all_prefs = await db.user_notification_prefs.find({}).to_list(None)
    prefs_by_user = {p["user_id"]: p for p in all_prefs}

    all_users = await db.users.find({"is_active": True}, {"id": 1, "_id": 0}).to_list(None)

    recipients = []
    for user in all_users:
        uid = user["id"]
        prefs = prefs_by_user.get(uid)

        if prefs and not prefs.get("enabled", True):
            continue

        if notif_type == "FAULTLINE_ESCALATION":
            if prefs and not prefs.get("notify_faultline_escalations", True):
                continue
            # Filter by faultline interest list if configured
            if prefs and prefs.get("faultline_ids") and item:
                if item.get("faultline_id") not in prefs["faultline_ids"]:
                    continue

        elif notif_type == "HIGH_PRIORITY_ARTICLE":
            min_score = prefs.get("min_priority_score", 90) if prefs else 90
            if item and item.get("priority_score", 0) < min_score:
                continue

        elif notif_type == "PAOI_IMPACT":
            if prefs and not prefs.get("notify_paoi_impact", True):
                continue

        elif notif_type == "STATE_ESCALATION":
            if prefs and not prefs.get("notify_state_escalations", True):
                continue
            # Filter by region of interest if configured
            if prefs and prefs.get("regions_of_interest") and item:
                if item.get("state") not in prefs["regions_of_interest"]:
                    continue

        recipients.append(uid)

    return recipients


_CONCERN_RANK = {"STABLE": 0, "MONITOR": 1, "ELEVATED": 2, "CRITICAL": 3}


async def _compute_state_concern(db, state: str) -> tuple[str, int]:
    """
    Recompute concern level for a single state using the same formula as trends.py.
    Returns (concern_level, stability_score).
    Uses a rolling 7-day window (matching the Dashboard's default view).
    """
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    SEV_WEIGHTS = {"critical": 4, "high": 2, "medium": 1, "low": 0.3}
    metrics = {
        "sev_weight": 0.0,
        "early_count": 0,
        "late_count": 0,
        "actors": set(),
        "cross_border_count": 0,
        "total": 0,
    }

    from shared import intelligence_col
    mid_cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()

    async for item in intelligence_col.find(
        {"state": state, "published_at": {"$gte": cutoff}},
        {"severity": 1, "actors": 1, "is_cross_border": 1, "published_at": 1, "_id": 0}
    ):
        metrics["total"] += 1
        metrics["sev_weight"] += SEV_WEIGHTS.get(item.get("severity", "low"), 0.3)
        for a in (item.get("actors") or []):
            metrics["actors"].add(a)
        if item.get("is_cross_border"):
            metrics["cross_border_count"] += 1
        if item.get("published_at", "") >= mid_cutoff:
            metrics["late_count"] += 1
        else:
            metrics["early_count"] += 1

    if metrics["total"] == 0:
        return "STABLE", 100

    max_sev = max(metrics["sev_weight"], 1)
    max_actors = max(len(metrics["actors"]), 1)
    severity_load = metrics["sev_weight"] / max_sev
    velocity = 0.0
    if metrics["early_count"] > 0:
        velocity = min((metrics["late_count"] / max(metrics["early_count"], 1)) / 3, 1.0)
    elif metrics["late_count"] > 0:
        velocity = 0.8
    actor_spread = len(metrics["actors"]) / max_actors
    cross_border = metrics["cross_border_count"] / metrics["total"]

    concern = severity_load * 0.40 + velocity * 0.25 + actor_spread * 0.20 + cross_border * 0.15
    stability = max(0, round(100 - concern * 100))

    if stability >= 75:
        level = "STABLE"
    elif stability >= 50:
        level = "MONITOR"
    elif stability >= 25:
        level = "ELEVATED"
    else:
        level = "CRITICAL"

    return level, stability


async def check_and_notify_state_escalations(db, affected_states: list) -> None:
    """
    Compare current concern_level for each affected state against the last stored
    level. If it moved upward (e.g. STABLE→MONITOR), dispatch a STATE_ESCALATION
    notification and update the stored snapshot.
    """
    if not affected_states:
        return

    for state in set(affected_states):
        try:
            current_level, stability = await _compute_state_concern(db, state)
            current_rank = _CONCERN_RANK.get(current_level, 0)

            snapshot = await db.state_severity_snapshots.find_one({"state": state})
            prev_level = snapshot["concern_level"] if snapshot else "STABLE"
            prev_rank = _CONCERN_RANK.get(prev_level, 0)

            if current_rank > prev_rank:
                # Escalated — dispatch notification
                recipients = await resolve_system_notification_recipients(
                    db, "STATE_ESCALATION", {"state": state}
                )
                if recipients:
                    await create_and_dispatch_notification(
                        notif_type="STATE_ESCALATION",
                        title=f"State Alert: {state}",
                        body=(
                            f"{state} concern level has risen from {prev_level} "
                            f"to {current_level} (stability score: {stability})"
                        ),
                        payload={
                            "state": state,
                            "previous_level": prev_level,
                            "current_level": current_level,
                            "stability_score": stability,
                        },
                        deep_link=f"/trends?state={state}",
                        source_type="system",
                        source_id=None,
                        created_by=None,
                        recipient_user_ids=recipients,
                    )
                    logger.info(
                        f"STATE_ESCALATION notification: {state} {prev_level}→{current_level}"
                    )

            # Always update snapshot (persist latest level)
            now = datetime.now(timezone.utc).isoformat()
            await db.state_severity_snapshots.update_one(
                {"state": state},
                {"$set": {
                    "state": state,
                    "concern_level": current_level,
                    "stability_score": stability,
                    "updated_at": now,
                }},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"State escalation check failed for {state}: {e}")


async def _log_attempt(db, notification_id, recipient_id, user_id, channel, status, error=None):
    try:
        await db.notification_delivery_attempts.insert_one({
            "id": str(uuid.uuid4()),
            "notification_id": notification_id,
            "recipient_id": recipient_id,
            "user_id": user_id,
            "channel": channel,
            "status": status,
            "error_message": error,
            "attempted_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass  # logging failure must never break delivery
