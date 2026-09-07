"""
User activity tracking: login sessions + action log (relevance ratings,
manual uploads, training actions). Backs the User Management > Activity tab
(Currently Online + date-range Activity Report) and the Monday 08:00 IST
weekly report reminder.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from shared import db, user_sessions_col, user_action_log_col, logger

ONLINE_THRESHOLD_MIN = 5
AWAY_THRESHOLD_MIN = 30


async def start_session(user: dict, ip_address: str) -> str:
    """Create a new login session record. Returns the session_id to embed in the JWT."""
    session_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    await user_sessions_col.insert_one({
        "id": session_id,
        "user_id": user["id"],
        "username": user["username"],
        "role": user.get("role", "viewer"),
        "iod": user.get("iod", "IOD-1"),
        "login_at": now_iso,
        "last_activity_at": now_iso,
        "logout_at": None,
        "ip_address": ip_address or "",
    })
    return session_id


async def touch_session(session_id: str) -> None:
    """Bump a session's last-activity timestamp. Called on every authenticated
    request. Never raises — a tracking failure must not break the request."""
    if not session_id:
        return
    try:
        await user_sessions_col.update_one(
            {"id": session_id},
            {"$set": {"last_activity_at": datetime.now(timezone.utc).isoformat()}},
        )
    except Exception as e:
        logger.warning(f"Session touch failed for {session_id}: {e}")


async def end_session(session_id: str) -> None:
    """Mark a session logged out (precise online/duration signal instead of
    waiting for the away/offline staleness threshold)."""
    if not session_id:
        return
    try:
        await user_sessions_col.update_one(
            {"id": session_id},
            {"$set": {"logout_at": datetime.now(timezone.utc).isoformat()}},
        )
    except Exception as e:
        logger.warning(f"Session end failed for {session_id}: {e}")


async def log_action(user: dict, action_type: str, detail: str) -> None:
    """Record one attributed action: relevance_rating | manual_upload | training_action.
    Never raises — logging must not block the action it's recording."""
    try:
        await user_action_log_col.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "username": user["username"],
            "action_type": action_type,
            "detail": detail[:300],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"Action log failed for {user.get('username')}: {e}")


async def get_online_sessions() -> list[dict]:
    """Sessions active in the last AWAY_THRESHOLD_MIN minutes, not logged out.
    status: 'online' (<=5 min) or 'away' (<=30 min)."""
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=AWAY_THRESHOLD_MIN)).isoformat()
    online_cutoff = (now - timedelta(minutes=ONLINE_THRESHOLD_MIN)).isoformat()

    cursor = user_sessions_col.find(
        {"logout_at": None, "last_activity_at": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("last_activity_at", -1)

    results = []
    async for s in cursor:
        status = "online" if s["last_activity_at"] >= online_cutoff else "away"
        results.append({**s, "status": status})
    return results


def _duration_minutes(login_at: str, end_at: str) -> float:
    try:
        start = datetime.fromisoformat(login_at)
        end = datetime.fromisoformat(end_at)
        return round((end - start).total_seconds() / 60, 1)
    except (ValueError, TypeError):
        return 0.0


async def build_activity_report(date_from: str, date_to: str) -> dict:
    """Per-user breakdown of sessions + attributed actions in [date_from, date_to)
    (ISO date strings, e.g. '2026-09-01'). A session counts toward the range if
    it started within it; a session's duration is login_at -> logout_at, or
    login_at -> last_activity_at if never logged out (approximation for
    browser-closed / token-expired sessions)."""
    range_start = f"{date_from}T00:00:00"
    range_end = f"{date_to}T23:59:59.999999"

    sessions_by_user: dict[str, list[dict]] = {}
    async for s in user_sessions_col.find(
        {"login_at": {"$gte": range_start, "$lte": range_end}}, {"_id": 0}
    ).sort("login_at", 1):
        end_at = s.get("logout_at") or s["last_activity_at"]
        sessions_by_user.setdefault(s["username"], []).append({
            "login_at": s["login_at"],
            "logout_at": s.get("logout_at"),
            "duration_minutes": _duration_minutes(s["login_at"], end_at),
            "ip_address": s.get("ip_address", ""),
        })

    action_counts: dict[str, dict[str, int]] = {}
    async for a in user_action_log_col.find(
        {"timestamp": {"$gte": range_start, "$lte": range_end}}, {"_id": 0}
    ):
        counts = action_counts.setdefault(a["username"], {
            "relevance_rating": 0, "manual_upload": 0, "training_action": 0,
        })
        if a["action_type"] in counts:
            counts[a["action_type"]] += 1

    usernames = sorted(set(sessions_by_user) | set(action_counts))
    per_user = []
    for username in usernames:
        sessions = sessions_by_user.get(username, [])
        counts = action_counts.get(username, {
            "relevance_rating": 0, "manual_upload": 0, "training_action": 0,
        })
        per_user.append({
            "username": username,
            "login_count": len(sessions),
            "sessions": sessions,
            "relevance_ratings_given": counts["relevance_rating"],
            "manual_uploads": counts["manual_upload"],
            "training_actions": counts["training_action"],
        })

    return {
        "date_from": date_from,
        "date_to": date_to,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "users": per_user,
    }
