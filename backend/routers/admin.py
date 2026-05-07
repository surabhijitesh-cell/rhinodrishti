"""
Admin-only endpoints for Rhino Drishti.

GET  /api/admin/api-usage          — daily usage + cost for last 7 days
GET  /api/admin/api-usage/today    — today's cost + alert status
POST /api/admin/api-usage/threshold — set daily cost alert threshold (USD)
GET  /api/admin/api-usage/debug    — collection stats + full write-path test
"""

import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from usage_tracker import get_daily_summary, get_today_cost_usd, USD_TO_INR
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
    daily = await get_daily_summary(days)
    threshold_usd = await _get_threshold()
    return {
        "daily": daily,
        "threshold_usd": threshold_usd,
        "threshold_inr": round(threshold_usd * USD_TO_INR, 2),
        "usd_to_inr": USD_TO_INR,
    }


@router.get("/admin/api-usage/today")
async def get_today_usage():
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


@router.get("/admin/api-usage/debug")
async def debug_usage():
    """
    Full diagnostic. Tests:
      1. Raw insert+delete
      2. Exact upsert/$inc path (same as track_usage)
      3. Direct track_usage() call with MockUsage — leaves 1 real record in DB
    """
    result = {
        "collection_count": 0,
        "recent_docs": [],
        "test_insert": None,
        "test_upsert_inc": None,
        "test_track_usage": None,
        "errors": {},
    }

    # 1. Count
    try:
        result["collection_count"] = await db.api_usage.count_documents({})
    except Exception as e:
        result["errors"]["count"] = str(e)

    # 2. Recent docs
    try:
        docs = await db.api_usage.find({}, {"_id": 0}).sort("last_updated", -1).to_list(5)
        result["recent_docs"] = docs
    except Exception as e:
        result["errors"]["fetch"] = str(e)

    # 3. Raw insert+delete
    try:
        ins = await db.api_usage.insert_one({
            "date": "debug-test", "hour": 0, "model": "debug",
            "input_tokens": 1, "output_tokens": 1,
            "cache_read_tokens": 0, "cache_write_tokens": 0,
            "call_count": 1, "cost_usd": 0.0,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        })
        await db.api_usage.delete_one({"_id": ins.inserted_id})
        result["test_insert"] = "OK"
    except Exception as e:
        result["errors"]["insert"] = str(e)

    # 4. Exact upsert/$inc (same operation as track_usage)
    try:
        now = datetime.now(timezone.utc)
        ur = await db.api_usage.update_one(
            {"date": "debug-upsert-test", "hour": 0, "model": "debug"},
            {
                "$inc": {
                    "input_tokens": 100, "output_tokens": 50,
                    "cache_read_tokens": 0, "cache_write_tokens": 0,
                    "call_count": 1, "cost_usd": 0.00005,
                },
                "$set": {"last_updated": now.isoformat()},
                "$setOnInsert": {"date": "debug-upsert-test", "hour": 0, "model": "debug"},
            },
            upsert=True,
        )
        await db.api_usage.delete_one({"date": "debug-upsert-test"})
        result["test_upsert_inc"] = (
            f"OK — upserted={ur.upserted_id is not None}, modified={ur.modified_count}"
        )
    except Exception as e:
        result["errors"]["upsert_inc"] = str(e)
        result["errors"]["upsert_inc_trace"] = traceback.format_exc()

    # 5. Call track_usage() directly — leaves 1 real record so widget shows data
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
        result["test_track_usage"] = (
            f"OK — count before={before} after={after} (delta={after - before})"
        )
    except Exception as e:
        result["errors"]["track_usage"] = str(e)
        result["errors"]["track_usage_trace"] = traceback.format_exc()

    result["collection_count_after"] = await db.api_usage.count_documents({})
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
    return {
        "threshold_usd": body.threshold_usd,
        "threshold_inr": round(body.threshold_usd * USD_TO_INR, 2),
    }
