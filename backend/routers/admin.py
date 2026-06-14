"""
Admin-only endpoints for Rhino Drishti.

GET  /api/admin/api-usage              — daily usage + cost for last N days (all providers)
GET  /api/admin/api-usage/today        — today's cost + per-provider breakdown + alert
GET  /api/admin/api-usage/providers    — today's cost grouped by provider
POST /api/admin/api-usage/threshold    — set daily cost alert threshold (USD)
POST /api/admin/api-usage/threshold/provider — set per-provider sub-alert (USD)
GET  /api/admin/api-usage/forex        — current USD→INR rate

GET  /api/admin/filter-cascade/today       — today's funnel totals + savings
GET  /api/admin/filter-cascade/daily       — daily cascade history
GET  /api/admin/filter-cascade/recent      — last N cycle docs (table)
GET  /api/admin/filter-cascade/health      — health status (stage1 failopen, centroid)

GET  /api/admin/filter-settings            — current filter threshold settings
POST /api/admin/filter-settings            — update thresholds (applied to pipeline ≤5 min)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from shared import db

router = APIRouter()

DEFAULT_ALERT_THRESHOLD_USD = 15.0
DEFAULT_PROVIDER_THRESHOLDS = {
    "anthropic": 1.50,
    "gemini": 0.30,
    "openai": 0.20,
}


class ThresholdBody(BaseModel):
    threshold_usd: float


class ProviderThresholdBody(BaseModel):
    provider: str
    threshold_usd: float


async def _get_threshold() -> float:
    doc = await db.admin_settings.find_one({"key": "api_alert_threshold"})
    return doc["value"] if doc else DEFAULT_ALERT_THRESHOLD_USD


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
    from usage_tracker import get_usd_to_inr_sync
    rate = get_usd_to_inr_sync()
    return {
        "threshold_usd": body.threshold_usd,
        "threshold_inr": round(body.threshold_usd * rate, 2),
    }


@router.post("/admin/api-usage/threshold/provider")
async def set_provider_threshold(body: ProviderThresholdBody):
    if body.threshold_usd < 0:
        raise HTTPException(status_code=422, detail="threshold_usd must be >= 0")
    key = f"api_alert_threshold_provider_{body.provider}"
    await db.admin_settings.update_one(
        {"key": key},
        {"$set": {"key": key, "value": body.threshold_usd,
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    from usage_tracker import get_usd_to_inr_sync
    rate = get_usd_to_inr_sync()
    return {"provider": body.provider, "threshold_usd": body.threshold_usd,
            "threshold_inr": round(body.threshold_usd * rate, 2)}


@router.get("/admin/api-usage/forex")
async def get_forex():
    from usage_tracker import get_usd_to_inr
    rate = await get_usd_to_inr()
    return {"usd_to_inr": rate, "source": "exchangerate-api.com", "ttl_hours": 6}


@router.get("/admin/openrouter-credits")
async def get_openrouter_credits():
    """Live check of OpenRouter account credits and rate-limit status."""
    import os, httpx
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return {"error": "OPENROUTER_API_KEY not set", "status": "unknown"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://openrouter.ai/api/v1/auth/key",
                headers={"Authorization": f"Bearer {key}"},
            )
        if r.status_code != 200:
            return {"status": "api_error", "http_status": r.status_code, "body": r.text[:200]}
        data = r.json().get("data", {})
        limit = data.get("limit")          # None means unlimited (paid plan)
        usage = data.get("usage", 0)
        label = data.get("label", "")
        is_free_tier = limit is not None
        remaining = round(limit - usage, 4) if limit is not None else None
        exhausted = is_free_tier and remaining is not None and remaining <= 0
        return {
            "status": "exhausted" if exhausted else "ok",
            "label": label,
            "limit_usd": limit,
            "usage_usd": usage,
            "remaining_usd": remaining,
            "is_free_tier": is_free_tier,
            "rate_limit_requests_per_interval": data.get("rate_limit", {}).get("requests"),
            "rate_limit_interval": data.get("rate_limit", {}).get("interval"),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/admin/openrouter-fallback-status")
async def get_fallback_status():
    """Check whether the Anthropic Haiku fallback is currently active."""
    from llm_client import is_openrouter_exhausted, _openrouter_exhausted_until, clear_openrouter_exhausted
    import time
    active = is_openrouter_exhausted()
    remaining = max(0, round(_openrouter_exhausted_until - time.time())) if active else 0
    return {
        "fallback_active": active,
        "fallback_remaining_sec": remaining,
        "message": f"Anthropic Haiku fallback active for {remaining}s" if active else "OpenRouter primary active",
    }


@router.post("/admin/openrouter-fallback-clear")
async def clear_fallback():
    """Manually clear the OpenRouter exhaustion flag (e.g. after topping up credits)."""
    from llm_client import clear_openrouter_exhausted
    clear_openrouter_exhausted()
    return {"message": "OpenRouter exhaustion flag cleared — pipeline will use OpenRouter on next cycle"}


@router.get("/admin/openrouter-credit-warning")
async def get_credit_warning_status():
    """Current credit warning level — polled by Dashboard banner every 60 s."""
    from llm_client import get_credit_warning
    data = get_credit_warning()
    return {
        "level": data["level"],           # "ok" | "low" | "critical"
        "remaining_usd": data["remaining_usd"],
        "top_up_url": "https://openrouter.ai/credits",
    }


@router.get("/admin/api-usage/providers")
async def get_today_providers():
    """Today's cost broken down by provider, with sub-alert status."""
    try:
        from usage_tracker import get_today_cost_by_provider, get_usd_to_inr_sync
        rate = get_usd_to_inr_sync()
        by_provider = await get_today_cost_by_provider()

        result = {}
        for provider, defaults in DEFAULT_PROVIDER_THRESHOLDS.items():
            key = f"api_alert_threshold_provider_{provider}"
            doc = await db.admin_settings.find_one({"key": key})
            threshold = doc["value"] if doc else defaults
            data = by_provider.get(provider, {"cost_usd": 0.0, "call_count": 0,
                                              "input_tokens": 0, "output_tokens": 0})
            cost = data["cost_usd"]
            result[provider] = {
                **data,
                "cost_inr": round(cost * rate, 2),
                "threshold_usd": threshold,
                "threshold_inr": round(threshold * rate, 2),
                "pct_of_limit": round(cost / threshold * 100, 1) if threshold else 0,
                "alert": cost >= threshold,
            }
        return {"providers": result, "usd_to_inr": rate}
    except Exception as e:
        return {"providers": {}, "error": str(e)}


# ── Enhanced existing endpoints ────────────────────────────────────────────────

@router.get("/admin/api-usage")
async def get_api_usage(days: int = 7):
    try:
        from usage_tracker import get_daily_summary, get_daily_summary_by_provider, get_usd_to_inr_sync
        daily = await get_daily_summary(days)
        by_provider = await get_daily_summary_by_provider(days)
        threshold_usd = await _get_threshold()
        rate = get_usd_to_inr_sync()
        return {
            "daily": daily,
            "by_provider": by_provider,
            "threshold_usd": threshold_usd,
            "threshold_inr": round(threshold_usd * rate, 2),
            "usd_to_inr": rate,
        }
    except Exception as e:
        return {"daily": [], "by_provider": [], "threshold_usd": DEFAULT_ALERT_THRESHOLD_USD,
                "threshold_inr": 1260.0, "usd_to_inr": 84.0, "error": str(e)}


@router.get("/admin/api-usage/today")
async def get_today_usage():
    try:
        from usage_tracker import (get_today_cost_usd, get_today_cost_by_provider,
                                   get_today_hourly_by_provider, get_usd_to_inr_sync)
        threshold_usd = await _get_threshold()
        rate = get_usd_to_inr_sync()

        today_usd = await get_today_cost_usd()
        today_inr = round(today_usd * rate, 2)
        alert = today_usd >= threshold_usd

        by_provider = await get_today_cost_by_provider()
        hourly = await get_today_hourly_by_provider()

        # Per-provider sub-alert status
        for provider in by_provider:
            key = f"api_alert_threshold_provider_{provider}"
            doc = await db.admin_settings.find_one({"key": key})
            thr = doc["value"] if doc else DEFAULT_PROVIDER_THRESHOLDS.get(provider, 999)
            cost = by_provider[provider]["cost_usd"]
            by_provider[provider]["cost_inr"] = round(cost * rate, 2)
            by_provider[provider]["threshold_usd"] = thr
            by_provider[provider]["alert"] = cost >= thr

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return {
            "date": today,
            "today_usd": today_usd,
            "today_inr": today_inr,
            "threshold_usd": threshold_usd,
            "threshold_inr": round(threshold_usd * rate, 2),
            "alert": alert,
            "pct_of_limit": round((today_usd / threshold_usd) * 100, 1) if threshold_usd else 0,
            "by_provider": by_provider,
            "hourly": hourly,
            "usd_to_inr": rate,
        }
    except Exception as e:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return {"date": today, "today_usd": 0.0, "today_inr": 0.0,
                "threshold_usd": DEFAULT_ALERT_THRESHOLD_USD,
                "threshold_inr": 1260.0, "alert": False,
                "pct_of_limit": 0, "by_provider": {}, "hourly": [], "error": str(e)}


# ── Filter cascade endpoints ───────────────────────────────────────────────────

@router.get("/admin/filter-cascade/today")
async def filter_cascade_today():
    try:
        from filter_metrics import get_today_totals, get_cascade_health
        from usage_tracker import get_usd_to_inr_sync
        totals = await get_today_totals()
        health = await get_cascade_health()
        rate = get_usd_to_inr_sync()
        saved_inr = round(totals.get("est_cost_saved_usd", 0) * rate, 2)
        return {**totals, "est_cost_saved_inr": saved_inr, "health": health,
                "usd_to_inr": rate}
    except Exception as e:
        return {"cycles": 0, "error": str(e)}


@router.get("/admin/filter-cascade/daily")
async def filter_cascade_daily(days: int = 7):
    try:
        from filter_metrics import get_daily_cascade
        from usage_tracker import get_usd_to_inr_sync
        rate = get_usd_to_inr_sync()
        rows = await get_daily_cascade(days)
        for r in rows:
            r["est_cost_saved_inr"] = round(r.get("est_cost_saved_usd", 0) * rate, 2)
        return {"daily": rows, "usd_to_inr": rate}
    except Exception as e:
        return {"daily": [], "error": str(e)}


@router.get("/admin/filter-cascade/recent")
async def filter_cascade_recent(limit: int = 20):
    try:
        from filter_metrics import get_recent_cycles
        return {"cycles": await get_recent_cycles(limit)}
    except Exception as e:
        return {"cycles": [], "error": str(e)}


@router.get("/admin/filter-cascade/health")
async def filter_cascade_health():
    try:
        from filter_metrics import get_cascade_health
        return await get_cascade_health()
    except Exception as e:
        return {"status": "unknown", "error": str(e)}


# ── Filter threshold settings ─────────────────────────────────────────────────

FILTER_SETTINGS_KEY = "filter_thresholds"
FILTER_DEFAULTS = {
    "stage05_min_sim":  0.35,
    "stage05_enabled":  True,
    "stage1_enabled":   True,
    "stage2_max_scan":  200,
    "stage2_max_haiku": 25,
}


class FilterSettingsBody(BaseModel):
    stage05_min_sim:  Optional[float] = None   # 0.10 – 0.70
    stage05_enabled:  Optional[bool]  = None
    stage1_enabled:   Optional[bool]  = None
    stage2_max_scan:  Optional[int]   = None   # 50 – 500
    stage2_max_haiku: Optional[int]   = None   # 5 – 50


@router.get("/admin/filter-settings")
async def get_filter_settings():
    """Return current filter threshold settings (DB-backed, falls back to defaults)."""
    doc = await db.admin_settings.find_one({"key": FILTER_SETTINGS_KEY}, {"_id": 0})
    if not doc:
        return {**FILTER_DEFAULTS, "key": FILTER_SETTINGS_KEY, "source": "defaults"}
    return {**FILTER_DEFAULTS, **{k: v for k, v in doc.items() if k != "_id"},
            "source": "database"}


@router.post("/admin/filter-settings")
async def set_filter_settings(body: FilterSettingsBody):
    """
    Persist new filter thresholds to DB and apply them to live pipeline immediately.
    Pipeline reads from DB with a 5-min in-memory cache — changes take effect within 5 min.
    Stage 0.5 threshold is also applied in-process instantly via set_min_sim_threshold().
    """
    # Read current
    doc = await db.admin_settings.find_one({"key": FILTER_SETTINGS_KEY}) or {}
    current = {**FILTER_DEFAULTS, **{k: v for k, v in doc.items() if k not in ("_id", "key")}}

    # Apply partial updates with clamping
    updates = {}
    if body.stage05_min_sim is not None:
        updates["stage05_min_sim"] = max(0.10, min(0.70, body.stage05_min_sim))
    if body.stage05_enabled is not None:
        updates["stage05_enabled"] = body.stage05_enabled
    if body.stage1_enabled is not None:
        updates["stage1_enabled"] = body.stage1_enabled
    if body.stage2_max_scan is not None:
        updates["stage2_max_scan"] = max(50, min(500, body.stage2_max_scan))
    if body.stage2_max_haiku is not None:
        updates["stage2_max_haiku"] = max(5, min(50, body.stage2_max_haiku))

    new_settings = {**current, **updates}

    await db.admin_settings.update_one(
        {"key": FILTER_SETTINGS_KEY},
        {"$set": {
            "key": FILTER_SETTINGS_KEY,
            **new_settings,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )

    # Apply Stage 0.5 threshold in-process immediately (no wait for cache TTL)
    if "stage05_min_sim" in updates:
        try:
            from relevance_filter import set_min_sim_threshold
            set_min_sim_threshold(updates["stage05_min_sim"])
        except Exception as e:
            pass  # non-fatal — DB value picked up by next pipeline cycle

    # Invalidate pipeline settings cache so next cycle reads new values
    try:
        from routers.pipeline import invalidate_pipeline_settings_cache
        invalidate_pipeline_settings_cache()
    except Exception:
        pass

    return {"message": "Filter settings updated", "settings": new_settings}
