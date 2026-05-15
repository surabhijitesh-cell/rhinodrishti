"""
Filter cascade metrics — per-cycle audit trail.

Writes one doc to `filter_metrics` collection after each
analyze_unprocessed_items() cycle. Used by the admin monitoring panel.

Schema:
  _id, date, hour, started_at, ended_at, duration_seconds,
  source,
  items_scanned,
  stage0_rejected, stage0_pass,
  stage05_rejected, stage05_pass, stage05_skipped,
  stage1_rejected, stage1_pass, stage1_failopen,
  haiku_relevant, haiku_not_relevant, haiku_failed,
  est_haiku_calls_saved, est_cost_saved_usd
"""

import logging
import uuid
from datetime import datetime, timezone
from shared import db

logger = logging.getLogger(__name__)

# Haiku cost per classify call (rough estimate, ~800 input tokens avg)
_HAIKU_COST_PER_CALL_USD = 0.0007


async def record_cycle(
    *,
    source: str,
    started_at: datetime,
    items_scanned: int,
    stage0_rejected: int,
    stage05_rejected: int,
    stage05_skipped: int,
    stage1_rejected: int,
    stage1_failopen: int,
    haiku_relevant: int,
    haiku_not_relevant: int,
    haiku_failed: int,
) -> None:
    """Persist one filter cycle record. Non-fatal on error."""
    try:
        now = datetime.now(timezone.utc)
        duration = (now - started_at).total_seconds()

        stage0_pass = items_scanned - stage0_rejected
        stage05_pass = stage0_pass - stage05_rejected
        stage1_pass = stage05_pass - stage1_rejected
        haiku_total = haiku_relevant + haiku_not_relevant + haiku_failed

        # How many Haiku calls did the cascade avoid?
        est_saved = items_scanned - haiku_total
        est_cost_saved = max(0.0, est_saved * _HAIKU_COST_PER_CALL_USD)

        await db.filter_metrics.insert_one({
            "id": str(uuid.uuid4()),
            "date": now.strftime("%Y-%m-%d"),
            "hour": now.hour,
            "source": source,
            "started_at": started_at.isoformat(),
            "ended_at": now.isoformat(),
            "duration_seconds": round(duration, 1),
            "items_scanned": items_scanned,
            "stage0_rejected": stage0_rejected,
            "stage0_pass": stage0_pass,
            "stage05_rejected": stage05_rejected,
            "stage05_pass": stage05_pass,
            "stage05_skipped": stage05_skipped,
            "stage1_rejected": stage1_rejected,
            "stage1_pass": stage1_pass,
            "stage1_failopen": stage1_failopen,
            "haiku_relevant": haiku_relevant,
            "haiku_not_relevant": haiku_not_relevant,
            "haiku_failed": haiku_failed,
            "est_haiku_calls_saved": est_saved,
            "est_cost_saved_usd": round(est_cost_saved, 4),
        })
    except Exception as e:
        logger.warning(f"filter_metrics.record_cycle failed: {e}")


async def get_today_totals() -> dict:
    """Aggregate all today's cycles into a single funnel dict."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pipeline = [
        {"$match": {"date": today}},
        {"$group": {
            "_id": None,
            "cycles": {"$sum": 1},
            "items_scanned":       {"$sum": "$items_scanned"},
            "stage0_rejected":     {"$sum": "$stage0_rejected"},
            "stage0_pass":         {"$sum": "$stage0_pass"},
            "stage05_rejected":    {"$sum": "$stage05_rejected"},
            "stage05_pass":        {"$sum": "$stage05_pass"},
            "stage05_skipped":     {"$sum": "$stage05_skipped"},
            "stage1_rejected":     {"$sum": "$stage1_rejected"},
            "stage1_pass":         {"$sum": "$stage1_pass"},
            "stage1_failopen":     {"$sum": "$stage1_failopen"},
            "haiku_relevant":      {"$sum": "$haiku_relevant"},
            "haiku_not_relevant":  {"$sum": "$haiku_not_relevant"},
            "haiku_failed":        {"$sum": "$haiku_failed"},
            "est_haiku_calls_saved": {"$sum": "$est_haiku_calls_saved"},
            "est_cost_saved_usd":  {"$sum": "$est_cost_saved_usd"},
            "avg_duration":        {"$avg": "$duration_seconds"},
        }},
    ]
    docs = await db.filter_metrics.aggregate(pipeline).to_list(length=1)
    if not docs:
        return {"cycles": 0, "items_scanned": 0}
    d = docs[0]
    d.pop("_id", None)
    d["avg_duration"] = round(d.get("avg_duration", 0), 1)
    d["est_cost_saved_usd"] = round(d.get("est_cost_saved_usd", 0), 4)
    return d


async def get_daily_cascade(days: int = 7) -> list[dict]:
    """Per-day cascade totals for trend chart."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    pipeline = [
        {"$match": {"date": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$date",
            "items_scanned":     {"$sum": "$items_scanned"},
            "stage0_rejected":   {"$sum": "$stage0_rejected"},
            "stage05_rejected":  {"$sum": "$stage05_rejected"},
            "stage1_rejected":   {"$sum": "$stage1_rejected"},
            "haiku_relevant":    {"$sum": "$haiku_relevant"},
            "haiku_not_relevant": {"$sum": "$haiku_not_relevant"},
            "est_cost_saved_usd": {"$sum": "$est_cost_saved_usd"},
            "cycles":            {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]
    docs = await db.filter_metrics.aggregate(pipeline).to_list(length=days + 1)
    return [{"date": d["_id"], **{k: v for k, v in d.items() if k != "_id"}}
            for d in docs]


async def get_recent_cycles(limit: int = 20) -> list[dict]:
    """Last N cycle docs for table view."""
    docs = await db.filter_metrics.find(
        {}, {"_id": 0}
    ).sort("started_at", -1).limit(limit).to_list(limit)
    return docs


async def get_cascade_health() -> dict:
    """Health signal: stage 1 fail-open rate (24h), centroid age."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    pipeline = [
        {"$match": {"started_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": None,
            "total_stage1_pass": {"$sum": "$stage1_pass"},
            "total_failopen":    {"$sum": "$stage1_failopen"},
            "cycles_24h":        {"$sum": 1},
        }},
    ]
    docs = await db.filter_metrics.aggregate(pipeline).to_list(length=1)
    if not docs:
        failopen_rate = 0.0
        cycles_24h = 0
    else:
        d = docs[0]
        total = d["total_stage1_pass"] or 1
        failopen_rate = round(d["total_failopen"] / total * 100, 1)
        cycles_24h = d["cycles_24h"]

    # Centroid age from relevance_filter module
    centroid_info: dict = {}
    try:
        from relevance_filter import get_filter_stats
        centroid_info = get_filter_stats()
    except Exception:
        pass

    # Stage 1 key present? (Stage 1 uses OpenRouter, not direct Gemini key)
    stage1_key_present = bool(__import__("os").environ.get("OPENROUTER_API_KEY", ""))

    # Threshold rationale:
    # - Circuit-breaker fail-opens (quota cooldown) are expected and not true failures.
    # - failing:  >85% AND key missing → Stage 1 essentially non-functional
    # - degraded: >40% → persistent errors beyond normal quota blips
    # - healthy:  ≤40%
    # Note: historical 24h rate can be temporarily elevated after a fix deployment;
    # key presence is the primary signal for hard "failing" status.
    status = "healthy"
    if not stage1_key_present:
        status = "failing"
    elif failopen_rate > 85:
        status = "failing"
    elif failopen_rate > 40:
        status = "degraded"

    import time
    centroid_age_h = round((time.time() - centroid_info.get("last_built_at", 0)) / 3600, 1)

    return {
        "status": status,
        "stage1_key_present": stage1_key_present,
        "stage1_failopen_rate_pct": failopen_rate,
        "cycles_last_24h": cycles_24h,
        "centroid_ready": centroid_info.get("centroid_built", False),
        "centroid_ref_items": centroid_info.get("reference_items", 0),
        "centroid_min_sim": centroid_info.get("min_sim_threshold", 0.25),
        "centroid_age_hours": centroid_age_h,
        "centroid_refresh_interval_hours": centroid_info.get("refresh_interval_seconds", 21600) / 3600,
    }
