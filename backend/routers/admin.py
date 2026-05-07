"""
Admin-only endpoints for Rhino Drishti.

GET  /api/admin/api-usage          — daily usage + cost for last 7 days
GET  /api/admin/api-usage/today    — today's cost + alert status
POST /api/admin/api-usage/threshold — set daily cost alert threshold (USD)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from shared import db

router = APIRouter()

DEFAULT_ALERT_THRESHOLD_USD = 15.0


class ThresholdBody(BaseModel):
    threshold_usd: float


async def _get_threshold() -> float:
    doc = await db.admin_settings.find_one({"key": "api_alert_threshold"})
    return doc["value"] if doc else DEFAULT_ALERT_THRESHOLD_USD


@router.get("/admin/api-usage")
async def get_api_usage(days: int = 7):
    try:
        from usage_tracker import get_daily_summary, USD_TO_INR
        daily = await get_daily_summary(days)
        threshold_usd = await _get_threshold()
        return {
            "daily": daily,
            "threshold_usd": threshold_usd,
            "threshold_inr": round(threshold_usd * USD_TO_INR, 2),
            "usd_to_inr": USD_TO_INR,
        }
    except Exception as e:
        return {"daily": [], "threshold_usd": DEFAULT_ALERT_THRESHOLD_USD,
                "threshold_inr": 1260.0, "usd_to_inr": 84.0, "error": str(e)}


@router.get("/admin/api-usage/today")
async def get_today_usage():
    try:
        from usage_tracker import get_today_cost_usd, USD_TO_INR
        threshold_usd = await _get_threshold()
        today_usd = await get_today_cost_usd()
        today_inr = round(today_usd * USD_TO_INR, 2)
        alert = today_usd >= threshold_usd

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
            "date": today,
            "today_usd": today_usd,
            "today_inr": today_inr,
            "threshold_usd": threshold_usd,
            "threshold_inr": round(threshold_usd * USD_TO_INR, 2),
            "alert": alert,
            "pct_of_limit": round((today_usd / threshold_usd) * 100, 1) if threshold_usd else 0,
            "hourly": hourly,
        }
    except Exception as e:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return {
            "date": today, "today_usd": 0.0, "today_inr": 0.0,
            "threshold_usd": DEFAULT_ALERT_THRESHOLD_USD,
            "threshold_inr": 1260.0, "alert": False,
            "pct_of_limit": 0, "hourly": [], "error": str(e),
        }


@router.get("/admin/api-usage/debug")
async def debug_usage():
    import traceback as tb
    result = {"collection_count": 0, "test_write": None, "track_usage_test": None, "errors": {}}
    try:
        result["collection_count"] = await db.api_usage.count_documents({})
    except Exception as e:
        result["errors"]["count"] = str(e)
    try:
        ins = await db.api_usage.insert_one({"_debug": True})
        await db.api_usage.delete_one({"_id": ins.inserted_id})
        result["test_write"] = "OK"
    except Exception as e:
        result["errors"]["write"] = str(e)
    try:
        from usage_tracker import track_usage

        class MockUsage:
            input_tokens = 500
            output_tokens = 200
            cache_read_input_tokens = 0
            cache_creation_input_tokens = 0

        before = await db.api_usage.count_documents({})
        await track_usage(MockUsage(), "claude-3-haiku-20240307")
        after = await db.api_usage.count_documents({})
        result["track_usage_test"] = f"OK delta={after - before}"
        result["collection_count"] = after
    except Exception as e:
        result["errors"]["track_usage"] = str(e)
        result["errors"]["trace"] = tb.format_exc()
    return result


@router.post("/admin/api-usage/threshold")
async def set_threshold(body: ThresholdBody):
    if body.threshold_usd <= 0:
        raise HTTPException(status_code=422, detail="threshold_usd must be > 0")
    await db.admin_settings.update_one(
        {"key": "api_alert_threshold"},
        {"$set": {"key": "api_alert_threshold", "value": body.threshold_usd,
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    from usage_tracker import USD_TO_INR
    return {
        "threshold_usd": body.threshold_usd,
        "threshold_inr": round(body.threshold_usd * USD_TO_INR, 2),
    }
