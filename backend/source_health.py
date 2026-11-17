"""Per-source health: last success, last error, so a silent source is noticed.

One document per source in `source_health`, keyed by "<kind>:<name>".
Recording never raises — health bookkeeping must not break a fetch.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# How long each kind of source may stay silent before the monitor warns.
SILENT_AFTER_HOURS = {
    "rss": 12, "youtube": 12, "telegram": 12, "web": 48, "apify": 96,
}
DEFAULT_SILENT_AFTER_HOURS = 24


def _key(kind: str, name: str) -> str:
    return f"{kind}:{name}"


async def record_success(db, kind: str, name: str, items: int = 0) -> None:
    now = datetime.now(timezone.utc).isoformat()
    try:
        await db.source_health.update_one(
            {"key": _key(kind, name)},
            {"$set": {"kind": kind, "name": name, "last_success": now, "last_items": items},
             "$inc": {"ok_count": 1}},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"source_health success write failed for {kind}:{name}: {e}")


async def record_error(db, kind: str, name: str, error: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    try:
        await db.source_health.update_one(
            {"key": _key(kind, name)},
            {"$set": {"kind": kind, "name": name, "last_error": str(error)[:300], "last_error_at": now},
             "$inc": {"error_count": 1}},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"source_health error write failed for {kind}:{name}: {e}")


def health_status(doc: dict, now: datetime) -> str:
    """'ok' | 'silent' | 'failing' | 'never' for one source_health document."""
    last_ok = doc.get("last_success")
    if not last_ok:
        return "failing" if doc.get("last_error") else "never"
    limit = SILENT_AFTER_HOURS.get(doc.get("kind"), DEFAULT_SILENT_AFTER_HOURS)
    hours = (now - datetime.fromisoformat(last_ok)).total_seconds() / 3600
    if hours <= limit:
        return "ok"
    return "failing" if (doc.get("last_error_at") or "") > last_ok else "silent"
