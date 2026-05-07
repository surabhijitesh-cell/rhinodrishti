"""
Admin-only endpoints for Rhino Drishti.

GET  /api/admin/api-usage          — daily usage + cost for last 7 days
GET  /api/admin/api-usage/today    — today's cost + alert status
POST /api/admin/api-usage/threshold — set daily cost alert threshold (USD)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from usage_tracker import get_daily_summary, get_today_cost_usd, USD_TO_INR
from shared import db

router = APIRouter()

DEFAULT_ALERT_THRESHOLD_USD = 15.0   # alert when daily cost exceeds $15


class ThresholdBody(BaseModel):
    threshold_usd: float


async def _get_threshold() -> float:
    doc = await db.admin_settings.find_one({"key": "api_alert_threshold"})
    return doc["value"] if doc else DEFAULT_ALERT_THRESHOLD_USD


@router.get("/admin/api-usage")
async def get_api_usage(days: int = 7):
    """Return daily usage summary for the last N days."""
    daily = await get_daily_summary(days)
    threshold_usd = await _get_threshold()
    return {
        "daily": daily,
        "threshold_usd": threshold_usd,
        "threshold_inr": round(threshold_usd * USD_TO_INR, 2),
        "usd_to_inr":    USD_TO_INR,
    }


@router.get("/admin/api-usage/today")
async def get_today_usage():
    """
    Today's cost and whether the alert threshold is exceeded.
    Polled by the frontend every 5 minutes to trigger alert popups.
    """
    threshold_usd = await _get_threshold()
    today_usd     = await get_today_cost_usd()
    today_inr     = round(today_usd * USD_TO_INR, 2)
    alert         = today_usd >= threshold_usd

    # Also pull today's hourly breakdown for the spark-line
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    hourly_raw = await db.api_usage.find(
        {"date": today},
        {"_id": 0, "hour": 1, "cost_usd": 1, "call_count": 1,
         "input_tokens": 1, "output_tokens": 1,
         "cache_read_tokens": 1, "cache_write_tokens": 1},
    ).sort("hour", 1).to_list(24)

    hourly = [
        {**h, "cost_inr": round(h["cost_usd"] * USD_TO_INR, 2)}
        for h in hourly_raw
    ]

    return {
        "date":          today,
        "today_usd":     today_usd,
        "today_inr":     today_inr,
        "threshold_usd": threshold_usd,
        "threshold_inr": round(threshold_usd * USD_TO_INR, 2),
        "alert":         alert,
        "pct_of_limit":  round((today_usd / threshold_usd) * 100, 1) if threshold_usd else 0,
        "hourly":        hourly,
    }


@router.post("/admin/api-usage/threshold")
async def set_threshold(body: ThresholdBody):
    """Update the daily cost alert threshold."""
    if body.threshold_usd <= 0:
        raise HTTPException(status_code=422, detail="threshold_usd must be > 0")
    await db.admin_settings.update_one(
        {"key": "api_alert_threshold"},
        {"$set": {"key": "api_alert_threshold", "value": body.threshold_usd,
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {
        "threshold_usd": body.threshold_usd,
        "threshold_inr": round(body.threshold_usd * USD_TO_INR, 2),
    }
