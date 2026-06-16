"""VAPID web push delivery via pywebpush."""
import os
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("push")

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL", "admin@rhinodrishti.local")


async def send_push_to_user(db, user_id: str, notif_doc: dict) -> None:
    """Send a web push notification to all active subscriptions for user_id."""
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        return  # VAPID not configured — silent no-op

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("pywebpush not installed — push delivery disabled")
        return

    subs = await db.push_subscriptions.find(
        {"user_id": user_id, "active": True}
    ).to_list(None)

    payload = json.dumps({
        "title": notif_doc.get("title", "Rhino Drishti"),
        "body": notif_doc.get("body", ""),
        "deep_link": notif_doc.get("deep_link", "/"),
        "notification_id": notif_doc.get("id", ""),
        "icon": "/icon-192.png",
        "badge": "/badge-72.png",
    })

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                },
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{VAPID_CLAIM_EMAIL}"},
            )
            await db.push_subscriptions.update_one(
                {"id": sub["id"]},
                {"$set": {
                    "last_success_at": datetime.now(timezone.utc).isoformat(),
                    "consecutive_failures": 0,
                }}
            )
        except Exception as e:
            err_str = str(e)
            status_code = 0
            try:
                from pywebpush import WebPushException as WPE
                if isinstance(e, WPE) and getattr(e, "response", None) is not None:
                    status_code = e.response.status_code
            except Exception:
                pass

            is_dead = status_code in (400, 404, 410)
            update_fields = {
                "last_failure_at": datetime.now(timezone.utc).isoformat(),
                "failure_reason": err_str[:200],
            }
            if is_dead:
                update_fields["active"] = False

            await db.push_subscriptions.update_one(
                {"id": sub["id"]},
                {"$set": update_fields, "$inc": {"consecutive_failures": 1}}
            )

            if not is_dead:
                fresh = await db.push_subscriptions.find_one({"id": sub["id"]})
                if fresh and fresh.get("consecutive_failures", 0) >= 3:
                    await db.push_subscriptions.update_one(
                        {"id": sub["id"]}, {"$set": {"active": False}}
                    )

            logger.warning(f"Push failed for user {user_id} sub {sub['endpoint'][:40]}…: {err_str[:80]}")
