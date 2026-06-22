"""
Faultline Intelligence — API endpoints.

Endpoints (declaration order matters for FastAPI path matching — fixed paths
are declared BEFORE the `/{fl_id}` catch-all):

  POST   /api/faultlines/seed                              — seed/update faultline registry
  GET    /api/faultlines                                   — list all faultlines (optional state filter)
  GET    /api/faultlines/dashboard-summary                 — top stressed faultlines for dashboard pulse strip
  GET    /api/faultlines/warnings                          — active un-ack'd alerts (warning banner)
  POST   /api/faultlines/warnings/{alert_id}/ack           — acknowledge an alert
  POST   /api/faultlines/run-daily                         — trigger daily pass (manual / debug)
  POST   /api/faultlines/backfill                          — kick off historical backfill
  GET    /api/faultlines/backfill/status                   — backfill progress
  GET    /api/faultlines/report?year=&month=               — standalone faultline-only PDF report
  GET    /api/faultlines/{fl_id}                           — single faultline + latest score
  PATCH  /api/faultlines/{fl_id}                           — update notes / active flag
  GET    /api/faultlines/{fl_id}/history?days=30           — daily score history (trendline)
  GET    /api/faultlines/{fl_id}/articles?date=&limit=     — matched articles + rationale

Auth:
  - All write endpoints (POST/PATCH) require `get_current_user`.
  - Admin-only endpoints (seed, backfill, run-daily, report) gate further on
    user.role in {"admin", "analyst"}.
  - Public reads (list, detail, history, articles, warnings, dashboard-summary)
    still require an authenticated user — match the project convention.
"""
import asyncio
import io
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from shared import db, logger
from utils.auth import get_current_user
from faultline_seed import seed_faultlines, FAULTLINES, STATE_TO_REGIONS
from priority_areas_seed import seed_priority_areas, PRIORITY_AREAS
from faultline_engine import (
    run_daily_faultline_pass,
    run_incremental_faultline_pass,
    run_backfill,
    _score_level,
    ALERT_EXPIRY_HOURS,
)

router = APIRouter()

faultlines_col = db.faultlines
scores_col = db.faultline_scores
mappings_col = db.faultline_mappings
priority_areas_col = db.priority_areas
alerts_col = db.faultline_alerts
backfill_status_col = db.faultline_backfill_status


# ── Models ────────────────────────────────────────────────────────────────────
class FaultlinePatch(BaseModel):
    active: Optional[bool] = None
    notes: Optional[str] = None
    manual_review_required: Optional[bool] = None


class PAOICreate(BaseModel):
    name: str
    description: Optional[str] = ""
    rank: Optional[int] = None
    geography: Optional[list] = []
    actors_of_interest: Optional[list] = []
    linked_faultline_ids: Optional[list] = []
    keyword_pull: Optional[dict] = None  # {keywords: [], regions: []}
    watch_geography: Optional[list] = []
    color: Optional[str] = "red"


class PAOIUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rank: Optional[int] = None
    geography: Optional[list] = None
    actors_of_interest: Optional[list] = None
    linked_faultline_ids: Optional[list] = None
    keyword_pull: Optional[dict] = None
    watch_geography: Optional[list] = None
    color: Optional[str] = None
    enabled: Optional[bool] = None


# ── Auth helper ───────────────────────────────────────────────────────────────
def _require_analyst_or_admin(current_user: dict) -> None:
    """Gate state-changing endpoints to analyst/admin roles only."""
    if current_user.get("role") not in ("admin", "analyst"):
        raise HTTPException(
            status_code=403,
            detail="Only analysts and admins can trigger faultline operations",
        )


# ── Helpers ───────────────────────────────────────────────────────────────────
async def _attach_latest_score(fl: dict) -> dict:
    """Add latest score snapshot to a faultline dict."""
    latest = await scores_col.find_one(
        {"faultline_id": fl["id"]},
        {"_id": 0},
        sort=[("date", -1)],
    )
    fl["latest_score"] = latest
    return fl


async def _is_alert_active(alert: dict) -> bool:
    """Alert is active if un-ack'd AND not expired."""
    if alert.get("acknowledged"):
        return False
    expires = alert.get("expires_at")
    if not expires:
        return True
    try:
        exp_dt = datetime.fromisoformat(expires)
        return exp_dt > datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return True


async def _backfill_already_running() -> bool:
    """Check if a backfill job is currently in 'running' status."""
    existing = await backfill_status_col.find_one(
        {"status": "running"}, {"_id": 0, "job_id": 1, "started_at": 1}
    )
    if not existing:
        return False
    # Stale-job protection: if a job has been "running" for > 24h, assume
    # crashed and let a new one start.
    started = existing.get("started_at")
    if started:
        try:
            started_dt = datetime.fromisoformat(started)
            if (datetime.now(timezone.utc) - started_dt).total_seconds() > 86400:
                await backfill_status_col.update_one(
                    {"job_id": existing["job_id"]},
                    {"$set": {"status": "stale", "finished_at": datetime.now(timezone.utc).isoformat()}},
                )
                return False
        except (ValueError, TypeError):
            pass
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# FIXED-PATH ROUTES (must be declared BEFORE /{fl_id} catch-all)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Seed ──────────────────────────────────────────────────────────────────────
@router.post("/faultlines/seed")
async def seed_faultline_registry(
    current_user: dict = Depends(get_current_user),
):
    """Seed (or refresh) the faultline registry from faultline_seed.FAULTLINES. Idempotent."""
    _require_analyst_or_admin(current_user)
    result = await seed_faultlines(db)
    return {"status": "ok", **result}


# ── Priority Areas of Interest (PAOI) ─────────────────────────────────────────
@router.post("/faultlines/priority-areas/seed")
async def seed_priority_area_registry(
    current_user: dict = Depends(get_current_user),
):
    """Seed PAOIs + tag faultlines with priority_area_ids. Idempotent.
    Run AFTER /faultlines/seed (it tags existing faultlines)."""
    _require_analyst_or_admin(current_user)
    result = await seed_priority_areas(db)
    return {"status": "ok", **result}


@router.get("/faultlines/priority-areas")
async def list_priority_areas(
    include_scores: bool = Query(True),
    current_user: dict = Depends(get_current_user),
):
    """
    List PAOIs ranked. With include_scores, attaches the current aggregate
    status of each PAOI: the max + avg score of its linked faultlines (latest
    snapshot per faultline), plus the dominant (highest-scoring) faultline.
    """
    cursor = priority_areas_col.find({"enabled": True}, {"_id": 0}).sort("rank", 1)
    paois = [p async for p in cursor]

    if not include_scores:
        return {"total": len(paois), "priority_areas": paois}

    # Latest score per faultline (one aggregation, reused across PAOIs)
    pipeline = [
        {"$sort": {"date": -1}},
        {"$group": {"_id": "$faultline_id", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$project": {"_id": 0, "faultline_id": 1, "faultline_name": 1,
                      "score": 1, "level": 1, "date": 1}},
    ]
    latest = {s["faultline_id"]: s async for s in scores_col.aggregate(pipeline)}

    for pa in paois:
        fl_ids = pa.get("linked_faultline_ids", [])
        scored = [latest[f] for f in fl_ids if f in latest]
        if scored:
            scores = [s["score"] for s in scored]
            top = max(scored, key=lambda s: s["score"])
            pa["status"] = {
                "max_score": round(max(scores), 1),
                "avg_score": round(sum(scores) / len(scores), 1),
                "level": _score_level(max(scores)),
                "dominant_faultline": {
                    "id": top["faultline_id"],
                    "name": top.get("faultline_name"),
                    "score": round(top["score"], 1),
                },
                "n_faultlines": len(scored),
                "as_of": max((s.get("date", "") for s in scored), default=None),
            }
        else:
            # Keyword-only PAOI (P3 LOC) or no scores yet
            pa["status"] = {
                "max_score": None, "avg_score": None, "level": "STABLE",
                "dominant_faultline": None, "n_faultlines": 0, "as_of": None,
            }

    return {"total": len(paois), "priority_areas": paois}


async def _retag_faultlines(now: str) -> int:
    """Re-derive faultline.priority_area_ids from current enabled PAOIs."""
    all_paois = await priority_areas_col.find({"enabled": True}, {"_id": 0}).to_list(None)
    await db.faultlines.update_many({}, {"$set": {"priority_area_ids": []}})
    fl_to_paois: dict[str, list] = {}
    for pa in all_paois:
        for fl_id in pa.get("linked_faultline_ids", []):
            fl_to_paois.setdefault(fl_id, []).append(pa["id"])
    tagged = 0
    for fl_id, paoi_ids in fl_to_paois.items():
        r = await db.faultlines.update_one(
            {"id": fl_id},
            {"$set": {"priority_area_ids": paoi_ids, "updated_at": now}},
        )
        if r.matched_count:
            tagged += 1
    return tagged


@router.post("/faultlines/priority-areas")
async def create_priority_area(
    data: PAOICreate,
    current_user: dict = Depends(get_current_user),
):
    _require_analyst_or_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    # Auto-assign rank if not provided
    if data.rank is None:
        count = await priority_areas_col.count_documents({})
        data.rank = count + 1

    # Generate a URL-safe id from name
    import re
    slug = re.sub(r"[^a-z0-9]+", "_", data.name.lower()).strip("_")
    pa_id = f"custom_{slug}"
    # Ensure unique
    existing = await priority_areas_col.find_one({"id": pa_id})
    if existing:
        pa_id = f"{pa_id}_{int(datetime.now(timezone.utc).timestamp())}"

    doc = {
        "id": pa_id,
        "rank": data.rank,
        "name": data.name,
        "description": data.description or "",
        "geography": data.geography or [],
        "actors_of_interest": data.actors_of_interest or [],
        "linked_faultline_ids": data.linked_faultline_ids or [],
        "keyword_pull": data.keyword_pull,
        "watch_geography": data.watch_geography or [],
        "color": data.color or "red",
        "enabled": True,
        "created_by": current_user.get("id"),
        "created_at": now,
        "updated_at": now,
    }
    await priority_areas_col.insert_one({**doc, "_id": pa_id})
    await _retag_faultlines(now)
    return doc


@router.put("/faultlines/priority-areas/{pa_id}")
async def update_priority_area(
    pa_id: str,
    data: PAOIUpdate,
    current_user: dict = Depends(get_current_user),
):
    _require_analyst_or_admin(current_user)
    existing = await priority_areas_col.find_one({"id": pa_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Priority area not found")

    now = datetime.now(timezone.utc).isoformat()
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    update["updated_at"] = now

    await priority_areas_col.update_one({"id": pa_id}, {"$set": update})
    await _retag_faultlines(now)

    updated = await priority_areas_col.find_one({"id": pa_id}, {"_id": 0})
    return updated


@router.delete("/faultlines/priority-areas/{pa_id}")
async def delete_priority_area(
    pa_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_analyst_or_admin(current_user)
    existing = await priority_areas_col.find_one({"id": pa_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Priority area not found")

    now = datetime.now(timezone.utc).isoformat()
    await priority_areas_col.update_one(
        {"id": pa_id},
        {"$set": {"enabled": False, "updated_at": now}},
    )
    await _retag_faultlines(now)
    return {"status": "disabled", "id": pa_id}


# ── List ──────────────────────────────────────────────────────────────────────
@router.get("/faultlines")
async def list_faultlines(
    state: Optional[str] = Query(None, description="Filter by state"),
    active_only: bool = Query(True),
    include_score: bool = Query(True),
    current_user: dict = Depends(get_current_user),
):
    """List all faultlines (optionally filtered)."""
    q: dict = {}
    if state:
        q["state"] = state
    if active_only:
        q["active"] = True

    cursor = faultlines_col.find(q, {"_id": 0}).sort([("state", 1), ("name", 1)])
    faultlines = [fl async for fl in cursor]

    if include_score:
        faultlines = await asyncio.gather(*[_attach_latest_score(fl) for fl in faultlines])

    return {"total": len(faultlines), "faultlines": faultlines}


# ── Dashboard summary ─────────────────────────────────────────────────────────
@router.get("/faultlines/dashboard-summary")
async def dashboard_summary(
    top_n: int = Query(5, ge=1, le=20),
    current_user: dict = Depends(get_current_user),
):
    """
    Top stressed faultlines (highest current score) for dashboard pulse strip.

    Uses per-faultline most-recent score (NOT a global "as_of" date) — so a
    faultline that hasn't been scored today still contributes its latest
    available snapshot. Returns level counts across all faultlines.
    """
    # Aggregation: per-faultline most recent doc by date
    pipeline = [
        {"$sort": {"date": -1}},
        {
            "$group": {
                "_id": "$faultline_id",
                "doc": {"$first": "$$ROOT"},
            }
        },
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$project": {"_id": 0}},
    ]
    cursor = scores_col.aggregate(pipeline)
    snapshots = [s async for s in cursor]

    if not snapshots:
        return {"top_stressed": [], "level_counts": {}, "as_of": None, "total_faultlines": 0}

    snapshots.sort(key=lambda s: s.get("score", 0), reverse=True)

    level_counts: dict[str, int] = {}
    for s in snapshots:
        lvl = s.get("level") or "STABLE"
        level_counts[lvl] = level_counts.get(lvl, 0) + 1

    most_recent_date = max((s.get("date", "") for s in snapshots), default=None)

    return {
        "as_of": most_recent_date,
        "top_stressed": snapshots[:top_n],
        "level_counts": level_counts,
        "total_faultlines": len(snapshots),
    }


# ── Warnings (alerts) ─────────────────────────────────────────────────────────
@router.get("/faultlines/warnings")
async def get_active_warnings(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """All active un-ack'd faultline alerts. Powers dashboard warning banner."""
    cursor = alerts_col.find(
        {"acknowledged": {"$ne": True}},
        {"_id": 0},
    ).sort("created_at", -1).limit(limit * 2)  # extra slack for expiry filtering
    alerts = [a async for a in cursor]

    active = [a for a in alerts if await _is_alert_active(a)]
    return {"total": len(active), "warnings": active[:limit]}


@router.post("/faultlines/warnings/{alert_id}/ack")
async def acknowledge_warning(
    alert_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Mark an alert as acknowledged (removes from warning banner).
    The acknowledger's identity is taken from the authenticated session, not
    a query parameter — prevents impersonation in the audit trail."""
    acked_by = current_user.get("username") or current_user.get("id") or "unknown"
    result = await alerts_col.update_one(
        {"id": alert_id, "acknowledged": {"$ne": True}},
        {"$set": {
            "acknowledged": True,
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
            "acknowledged_by": acked_by,
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Alert not found or already acknowledged")
    return {"status": "ok", "acknowledged_by": acked_by}


# ── Generation triggers ───────────────────────────────────────────────────────
@router.post("/faultlines/run-daily")
async def trigger_daily_pass(
    background_tasks: BackgroundTasks,
    target_date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to today"),
    current_user: dict = Depends(get_current_user),
):
    """Manually trigger the daily faultline scoring pass (debug / catch-up).
    Blocked if a backfill is currently running (concurrency guard)."""
    _require_analyst_or_admin(current_user)

    if await _backfill_already_running():
        raise HTTPException(
            409,
            "A backfill job is currently running. Wait for it to finish before triggering a manual pass.",
        )

    async def _bg():
        try:
            await run_daily_faultline_pass(db, target_date=target_date)
        except Exception as e:
            logger.exception(f"Manual faultline pass failed: {e}")
    background_tasks.add_task(_bg)
    return {"status": "started", "target_date": target_date or "today"}


@router.post("/faultlines/refresh")
async def trigger_incremental_pass(
    background_tasks: BackgroundTasks,
    lookback_hours: int = Query(6, ge=1, le=48, description="How many hours back to scan for new articles"),
    current_user: dict = Depends(get_current_user),
):
    """Keyword-only incremental pass across all active faultlines.

    Fast (seconds). No LLM calls. Use to pull in articles processed since the last
    full daily pass without waiting for the next scheduled run at 06:00/18:00 IST.
    Existing LLM-scored mappings are preserved; only new articles are inserted.
    """
    async def _bg():
        try:
            result = await run_incremental_faultline_pass(db, lookback_hours=lookback_hours)
            logger.info(f"Manual incremental faultline pass (all): {result}")
        except Exception as e:
            logger.exception(f"Manual incremental faultline pass failed: {e}")
    background_tasks.add_task(_bg)
    return {"status": "started", "lookback_hours": lookback_hours}


@router.post("/faultlines/{fl_id}/refresh")
async def trigger_faultline_refresh(
    fl_id: str,
    background_tasks: BackgroundTasks,
    lookback_hours: int = Query(24, ge=1, le=72, description="Hours back to scan for new articles"),
    current_user: dict = Depends(get_current_user),
):
    """Per-faultline incremental refresh — scans only for articles matching this faultline.

    Called by the refresh button on the faultline detail page. Keyword-only (no LLM),
    runs in seconds. Inserts any new matching articles into today's mappings.
    Returns immediately; UI should re-fetch article list after a short delay.
    """
    fl = await db.faultlines.find_one({"id": fl_id})
    if not fl:
        raise HTTPException(404, f"Faultline {fl_id} not found")

    async def _bg():
        try:
            result = await run_incremental_faultline_pass(
                db, lookback_hours=lookback_hours, faultline_id=fl_id
            )
            logger.info(f"Per-faultline refresh [{fl_id}]: {result}")
        except Exception as e:
            logger.exception(f"Per-faultline refresh [{fl_id}] failed: {e}")
    background_tasks.add_task(_bg)
    return {"status": "started", "faultline_id": fl_id, "lookback_hours": lookback_hours}


@router.post("/faultlines/backfill")
async def trigger_backfill(
    background_tasks: BackgroundTasks,
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD; default = earliest article"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD; default = today"),
    force: bool = Query(False, description="True = re-score every date (overwrite). False = resume (skip already-scored dates)."),
    current_user: dict = Depends(get_current_user),
):
    """
    Kick off historical backfill. Long-running (minutes to hours).
    Blocked if another backfill is already running (concurrency guard).

    force=false (default): RESUME mode — skips dates that already have scores.
      If a run dies mid-way, just re-fire and it continues from where it stopped.
    force=true: re-score every date in range, overwriting existing scores.
      Use this for the FIRST run after a scoring-logic change (old scores are
      stale and must be overwritten).
    """
    _require_analyst_or_admin(current_user)

    if await _backfill_already_running():
        raise HTTPException(
            409,
            "A backfill job is already running. Check /api/faultlines/backfill/status.",
        )

    job_id = f"backfill_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    await backfill_status_col.insert_one({
        "job_id": job_id,
        "status": "running",
        "start_date": start_date,
        "end_date": end_date,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "triggered_by": current_user.get("username") or current_user.get("id"),
        "force": force,
    })

    async def _bg():
        try:
            result = await run_backfill(
                db, start_date=start_date, end_date=end_date, resume=not force
            )
            await backfill_status_col.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "completed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "result": result,
                }},
            )
        except Exception as e:
            logger.exception("Backfill failed")
            await backfill_status_col.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "error",
                    "error": str(e)[:500],
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }},
            )

    background_tasks.add_task(_bg)
    return {"status": "started", "job_id": job_id}


@router.get("/faultlines/backfill/status")
async def backfill_status(
    current_user: dict = Depends(get_current_user),
):
    """Most recent backfill job status."""
    latest = await backfill_status_col.find_one(
        {}, {"_id": 0}, sort=[("started_at", -1)]
    )
    return latest or {"status": "no_jobs"}


# ── Standalone Faultline Analysis Report PDF (5 pages, Path B LLM) ────────────
@router.get("/faultlines/report")
async def faultline_pdf_report(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    current_user: dict = Depends(get_current_user),
):
    """
    Faultline Analysis Report PDF — 5 pages, shared visual identity with the
    Monthly Strategic Brief. Layout:
      P1  Cover + Key Metrics + MoM Level Distribution + LLM-written Bottom Line
      P2  Priority Areas of Interest (P1->P5) with reused PAOI synthesis
      P3  State-wise faultline tables + state narratives
      P4  Top 10 Movers with 3 news drivers each + LLM batched outlooks
      P5  Cross-cutting Manual Review Advisory + per-state advisory roll-up

    3 LLM calls (Path B): bottom line, batched mover outlooks, cross-state advisory.
    Reuses cached PAOI synthesis + state_narratives from the monthly brief.
    """
    from faultline_pdf import (
        aggregate_faultline_report, run_pdf_synthesis, render_faultline_pdf,
    )
    from routers.brief_monthly import _call_llm_json

    # Aggregate everything PDF needs (no LLM here)
    agg = await aggregate_faultline_report(db, year, month)
    if not agg.get("all_faultlines"):
        raise HTTPException(404, f"No faultline data for {year}-{month:02d}")

    # Run B1+B2+B3+B4 LLM synthesis in parallel
    synthesis = await run_pdf_synthesis(agg, _call_llm_json)

    # Load requesting user's watchlist priority map
    from shared import db as _db
    from routers.watchlist import watchlist_col as _wl_col
    username = current_user.get("username", "")
    priority_map: dict = {}
    if username:
        async for entry in _wl_col.find({"username": username}, {"faultline_id": 1, "rank": 1, "_id": 0}):
            priority_map[entry["faultline_id"]] = entry["rank"]

    # Render PDF
    pdf_bytes = render_faultline_pdf(agg, synthesis, priority_map=priority_map)

    filename = f"faultline_analysis_{year}_{month:02d}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Admin: force-clear a stuck backfill job ───────────────────────────────────
@router.post("/faultlines/admin/clear-stuck-backfill")
async def clear_stuck_backfill(
    current_user: dict = Depends(get_current_user),
):
    """
    Admin-only: mark any 'running' backfill job as 'stale'. Does NOT kill the
    underlying asyncio task — you must also restart the Render service to stop
    the actual runaway loop. After both steps you can re-trigger /backfill.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(403, "Admin only")

    result = await backfill_status_col.update_many(
        {"status": "running"},
        {"$set": {
            "status": "stale",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "cleared_by": current_user.get("username") or current_user.get("id"),
        }},
    )
    return {
        "status": "ok",
        "jobs_cleared": result.modified_count,
        "note": (
            "If a backfill loop is still running in the Render process, you must "
            "restart the Render service to actually stop it. This endpoint only "
            "clears the DB lock so a new backfill can start."
        ),
    }


# ── Admin: purge intelligence + score data before a cutoff date ───────────────
@router.post("/faultlines/admin/purge-before")
async def purge_before(
    cutoff: str = Query(..., description="YYYY-MM-DD. All data strictly before this date is deleted."),
    confirm: bool = Query(False, description="Must be true to actually delete. Defaults to dry-run."),
    current_user: dict = Depends(get_current_user),
):
    """
    Admin-only DESTRUCTIVE operation. Deletes from:
      - intelligence_items   (published_at < cutoff)
      - faultline_scores     (date < cutoff)
      - faultline_mappings   (date < cutoff)
      - intelligence_patterns (detected_at < cutoff)

    Use confirm=false (default) for a dry-run that reports counts without deleting.
    Use confirm=true to commit.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(403, "Admin only")

    # Validate cutoff format
    try:
        cutoff_date = datetime.fromisoformat(cutoff).date()
    except ValueError:
        raise HTTPException(400, f"Invalid cutoff date format: {cutoff}. Expected YYYY-MM-DD.")
    cutoff_iso = cutoff_date.isoformat()

    # Safety: refuse to purge anything inside the last 30 days
    floor = (datetime.now(timezone.utc).date() - timedelta(days=30)).isoformat()
    if cutoff_iso > floor:
        raise HTTPException(
            400,
            f"Refusing to purge within the last 30 days. cutoff={cutoff_iso}, floor={floor}",
        )

    # Count matches first (always — dry-run + confirmed)
    intel_count = await db.intelligence_items.count_documents(
        {"published_at": {"$lt": cutoff_iso}}
    )
    scores_count = await db.faultline_scores.count_documents(
        {"date": {"$lt": cutoff_iso}}
    )
    mappings_count = await db.faultline_mappings.count_documents(
        {"date": {"$lt": cutoff_iso}}
    )
    patterns_count = await db.intelligence_patterns.count_documents(
        {"detected_at": {"$lt": cutoff_iso}}
    )

    counts = {
        "intelligence_items": intel_count,
        "faultline_scores": scores_count,
        "faultline_mappings": mappings_count,
        "intelligence_patterns": patterns_count,
    }

    if not confirm:
        return {
            "status": "dry_run",
            "cutoff": cutoff_iso,
            "would_delete": counts,
            "total": sum(counts.values()),
            "hint": "Re-run with confirm=true to commit the delete.",
        }

    # Confirmed — execute deletes
    triggered_by = current_user.get("username") or current_user.get("id")
    logger.warning(
        f"Purging pre-{cutoff_iso} data: intel={intel_count}, "
        f"scores={scores_count}, mappings={mappings_count}, "
        f"patterns={patterns_count}. Triggered by {triggered_by}."
    )

    deleted = {}
    r = await db.intelligence_items.delete_many({"published_at": {"$lt": cutoff_iso}})
    deleted["intelligence_items"] = r.deleted_count
    r = await db.faultline_scores.delete_many({"date": {"$lt": cutoff_iso}})
    deleted["faultline_scores"] = r.deleted_count
    r = await db.faultline_mappings.delete_many({"date": {"$lt": cutoff_iso}})
    deleted["faultline_mappings"] = r.deleted_count
    r = await db.intelligence_patterns.delete_many({"detected_at": {"$lt": cutoff_iso}})
    deleted["intelligence_patterns"] = r.deleted_count

    return {
        "status": "ok",
        "cutoff": cutoff_iso,
        "deleted": deleted,
        "total": sum(deleted.values()),
        "triggered_by": triggered_by,
    }


# ── Custom faultline creation ─────────────────────────────────────────────────
class CustomFaultlineCreate(BaseModel):
    name: str
    state: str
    description: str
    keywords: Optional[list] = None


class KeywordRecommendRequest(BaseModel):
    name: str
    state: str
    description: str


@router.post("/faultlines/recommend-keywords")
async def recommend_keywords(
    body: KeywordRecommendRequest,
    current_user: dict = Depends(get_current_user),
):
    """Ask the LLM to suggest monitoring keywords for a custom faultline."""
    from routers.brief_monthly import _call_llm_json
    prompt = (
        f"You are an intelligence analyst. A user wants to monitor a new faultline:\n"
        f"Name: {body.name}\nState/Region: {body.state}\nDescription: {body.description}\n\n"
        f"Return a JSON object with a single key \"keywords\" whose value is a list of "
        f"10-15 specific search keywords or short phrases (English) most likely to surface "
        f"relevant news articles about this faultline. Focus on actors, locations, events, "
        f"and issue-specific terminology. No generic terms like 'violence' or 'protest'."
    )
    result = await _call_llm_json(prompt, max_tokens=400)
    keywords = result.get("keywords", [])
    if not isinstance(keywords, list):
        keywords = []
    return {"keywords": keywords[:20]}


@router.post("/faultlines")
async def create_custom_faultline(
    body: CustomFaultlineCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a user-defined custom faultline."""
    import uuid
    from datetime import datetime, timezone as _tz
    fl_id = f"custom_{uuid.uuid4().hex[:10]}"
    doc = {
        "id": fl_id,
        "name": body.name.strip(),
        "state": body.state.strip(),
        "description": body.description.strip(),
        "keywords": body.keywords or [],
        "active": True,
        "is_custom": True,
        "created_by": current_user.get("username"),
        "created_at": datetime.now(_tz.utc).isoformat(),
    }
    await faultlines_col.insert_one({**doc, "_id": fl_id})
    return {"status": "ok", "faultline": doc}


# ── Debug: pre-filter diagnostic ─────────────────────────────────────────────
@router.get("/faultlines/{fl_id}/debug-prefilter")
async def debug_prefilter(
    fl_id: str,
    days: int = Query(7, description="Look-back window in days"),
    current_user: dict = Depends(get_current_user),
):
    """
    Diagnostic endpoint: run Stage 1 + Stage 2 for a faultline and return counts.
    Tells you exactly where articles are being dropped.
    """
    from datetime import timezone as _tz2, timedelta as _td
    from faultline_engine import pre_filter_articles, match_subissues_to_article, _fetch_subissues, SUBISSUE_STRUCTURED_THRESHOLD
    from faultline_seed import STATE_TO_REGIONS

    fl = await faultlines_col.find_one({"id": fl_id}, {"_id": 0})
    if not fl:
        raise HTTPException(status_code=404, detail=f"Faultline '{fl_id}' not found")

    now = datetime.now(_tz2.utc)
    window_end = now + _td(days=1)
    window_start = now - _td(days=days)

    # Same article query as run_daily_faultline_pass
    articles = await db.intelligence_items.find(
        {
            "published_at": {"$gte": window_start.isoformat(), "$lt": window_end.isoformat()},
            "processed": True,
            "is_relevant": {"$ne": False},
            "is_archived": {"$ne": True},
        },
        {
            "id": 1, "title": 1, "ai_summary": 1, "source": 1,
            "published_at": 1, "severity": 1, "priority_score": 1, "tags": 1,
            "signal_bucket": 1, "regions": 1, "state": 1, "actors": 1,
            "district": 1, "why_it_matters": 1, "signal_strength": 1,
            "india_relevance_score": 1, "locations_mentioned": 1, "threat_category": 1,
            "entities": 1, "is_cross_border": 1, "threat_trajectory": 1,
        },
    ).to_list(length=5000)

    total_articles = len(articles)

    # Stage 1
    candidates = pre_filter_articles(fl, articles)

    # Explain why first few non-candidates failed (up to 10 samples)
    fl_state_regions = set(STATE_TO_REGIONS.get(fl["state"], [fl["state"]]))
    for region in list(fl_state_regions):
        if region in STATE_TO_REGIONS:
            fl_state_regions.update(STATE_TO_REGIONS[region])
    fl_keywords = [k.lower() for k in fl.get("keywords", [])]
    fl_tags = set(fl.get("tags", []))
    fl_buckets = set(fl.get("signal_buckets", []))
    fl_loc = [l.lower() for l in fl.get("loc_focus", [])]

    rejection_samples = []
    for art in articles[:200]:
        if art in candidates:
            continue
        if len(rejection_samples) >= 5:
            break
        art_regions = set(art.get("regions") or [])
        if art.get("state"):
            art_regions.add(art["state"])
        state_match = bool(art_regions & fl_state_regions)
        haystack = " ".join([
            (art.get("title") or "").lower(),
            (art.get("ai_summary") or "").lower(),
        ])
        tag_match = bool(set(art.get("tags") or []) & fl_tags)
        bucket_match = (art.get("signal_bucket") or "") in fl_buckets
        kw_match = any(kw in haystack for kw in fl_keywords)
        loc_match = any(lk in haystack for lk in fl_loc) if fl_loc else False
        rejection_samples.append({
            "title": (art.get("title") or "")[:80],
            "state": art.get("state"),
            "regions": art.get("regions"),
            "tags": art.get("tags"),
            "signal_bucket": art.get("signal_bucket"),
            "state_match": state_match,
            "tag_match": tag_match,
            "bucket_match": bucket_match,
            "kw_match": kw_match,
            "loc_match": loc_match,
            "why_rejected": "state_match=False" if not state_match else "no tag/bucket/kw/loc",
        })

    # Stage 2
    subissues = await _fetch_subissues(db, fl_id)
    stage2_pairs = []
    stage2_drops = []
    for art in candidates[:20]:
        matched = match_subissues_to_article(fl, art, subissues)
        if matched:
            stage2_pairs.append({
                "title": (art.get("title") or "")[:80],
                "subissues_matched": [m["subissue"]["name"] for m in matched],
                "scores": [round(m["structured_score"], 1) for m in matched],
            })
        else:
            stage2_drops.append({
                "title": (art.get("title") or "")[:80],
                "state": art.get("state"),
                "tags": art.get("tags"),
            })

    return {
        "faultline": fl_id,
        "window_days": days,
        "total_articles_in_window": total_articles,
        "stage1_pass": len(candidates),
        "stage2_pairs": len(stage2_pairs),
        "num_subissues": len(subissues),
        "fl_state_regions": sorted(fl_state_regions),
        "stage1_sample_candidates": [
            {"title": (c.get("title") or "")[:80], "state": c.get("state"), "regions": c.get("regions")}
            for c in candidates[:5]
        ],
        "stage1_rejection_samples": rejection_samples,
        "stage2_pairs_detail": stage2_pairs[:5],
        "stage2_drops": stage2_drops[:5],
    }


# ── Sub-issue seed ────────────────────────────────────────────────────────────
@router.post("/faultlines/seed-subissues")
async def seed_subissue_registry(
    current_user: dict = Depends(get_current_user),
):
    """Seed (or refresh) sub-issue registry from subissue_seed.SUBISSUE_SEED. Idempotent."""
    _require_analyst_or_admin(current_user)
    from subissue_seed import seed_subissues
    result = await seed_subissues(db)
    return {"status": "ok", **result}


# ── Faultline detail with sub-issues ─────────────────────────────────────────
@router.get("/faultlines/{fl_id}/detail")
async def get_faultline_detail(
    fl_id: str,
    date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to latest"),
    current_user: dict = Depends(get_current_user),
):
    """
    Return faultline score snapshot + dominant sub-issues with sample articles.
    Consumed by paoi_brief.py for narrative brief generation.
    """
    fl = await faultlines_col.find_one({"id": fl_id}, {"_id": 0})
    if not fl:
        raise HTTPException(status_code=404, detail=f"Faultline '{fl_id}' not found")

    score_query: dict = {"faultline_id": fl_id}
    if date:
        score_query["date"] = date
    score = await scores_col.find_one(score_query, {"_id": 0}, sort=[("date", -1)])

    if not score:
        return {"faultline": fl, "score": None, "dominant_subissues": [], "loc_risk": False}

    dominant = score.get("dominant_subissues", [])
    for d in dominant:
        sample_ids = d.get("sample_article_ids", [])[:3]
        if sample_ids:
            arts = await db.intelligence_items.find(
                {"id": {"$in": sample_ids}},
                {"id": 1, "title": 1, "published_at": 1, "severity": 1, "source": 1, "_id": 0},
            ).to_list(length=3)
            d["sample_articles"] = arts

    return {
        "faultline": fl,
        "score": score,
        "dominant_subissues": dominant,
        "loc_risk": score.get("loc_risk", False),
        "loc_segment": ", ".join(
            loc for d in dominant for loc in (d.get("loc_focus") or [])
        )[:200],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DYNAMIC-PATH ROUTES (catch-all `/{fl_id}` — must come LAST)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/faultlines/{fl_id}")
async def get_faultline(
    fl_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Single faultline with latest score + linked faultlines + active alert (if any)."""
    fl = await faultlines_col.find_one({"id": fl_id}, {"_id": 0})
    if not fl:
        raise HTTPException(404, f"Faultline '{fl_id}' not found")

    fl = await _attach_latest_score(fl)

    # Active alert
    cursor = alerts_col.find(
        {"faultline_id": fl_id, "acknowledged": {"$ne": True}},
        {"_id": 0},
    ).sort("created_at", -1).limit(1)
    alerts = [a async for a in cursor]
    fl["active_alert"] = None
    if alerts and await _is_alert_active(alerts[0]):
        fl["active_alert"] = alerts[0]

    # Linked faultline details (name + state)
    linked_ids = [lf["id"] for lf in fl.get("linked_faultlines", [])]
    if linked_ids:
        linked_docs = await faultlines_col.find(
            {"id": {"$in": linked_ids}},
            {"_id": 0, "id": 1, "name": 1, "state": 1},
        ).to_list(length=100)
        linked_map = {d["id"]: d for d in linked_docs}
        for lf in fl.get("linked_faultlines", []):
            target = linked_map.get(lf["id"])
            if target:
                lf["name"] = target["name"]
                lf["state"] = target["state"]

    return fl


@router.patch("/faultlines/{fl_id}")
async def update_faultline(
    fl_id: str,
    patch: FaultlinePatch,
    current_user: dict = Depends(get_current_user),
):
    """Update notes / active / manual_review_required flags."""
    _require_analyst_or_admin(current_user)

    update_doc: dict = {}
    if patch.active is not None:
        update_doc["active"] = patch.active
    if patch.notes is not None:
        # Cap at 5000 chars to prevent abuse
        update_doc["notes"] = patch.notes[:5000]
    if patch.manual_review_required is not None:
        update_doc["manual_review_required"] = patch.manual_review_required

    if not update_doc:
        raise HTTPException(400, "No fields to update")

    update_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_doc["updated_by"] = current_user.get("username") or current_user.get("id")
    result = await faultlines_col.update_one({"id": fl_id}, {"$set": update_doc})
    if result.matched_count == 0:
        raise HTTPException(404, f"Faultline '{fl_id}' not found")
    return {"status": "ok", "updated_fields": list(update_doc.keys())}


@router.get("/faultlines/{fl_id}/history")
async def get_faultline_history(
    fl_id: str,
    days: int = Query(30, ge=1, le=730),
    current_user: dict = Depends(get_current_user),
):
    """Daily score history for trendline chart."""
    fl = await faultlines_col.find_one({"id": fl_id}, {"_id": 0, "name": 1, "state": 1})
    if not fl:
        raise HTTPException(404, f"Faultline '{fl_id}' not found")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    cursor = scores_col.find(
        {"faultline_id": fl_id, "date": {"$gte": cutoff}},
        {"_id": 0, "date": 1, "score": 1, "level": 1, "n_articles": 1,
         "n_significant": 1, "avg_impact": 1, "avg_confidence": 1,
         "severity_load": 1, "velocity": 1, "actor_spread": 1, "cross_border": 1},
    ).sort("date", 1)
    series = [s async for s in cursor]

    return {
        "faultline_id": fl_id,
        "name": fl["name"],
        "state": fl["state"],
        "series": series,
        "days_requested": days,
        "points": len(series),
    }


@router.get("/faultlines/{fl_id}/articles")
async def get_faultline_articles(
    fl_id: str,
    date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to latest"),
    limit: int = Query(30, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """Matched articles for a faultline on a given day with rationale + evidence."""
    q: dict = {"faultline_id": fl_id}
    if date:
        q["date"] = date
    else:
        latest = await mappings_col.find_one(
            {"faultline_id": fl_id}, {"date": 1}, sort=[("date", -1)]
        )
        if not latest:
            return {"faultline_id": fl_id, "articles": [], "date": None}
        q["date"] = latest["date"]

    cursor = mappings_col.find(q, {"_id": 0}).sort(
        [("article_published_at", -1), ("impact_score", -1)]
    ).limit(limit)
    mappings = [m async for m in cursor]

    # Fetch source article URLs for navigation
    article_ids = [m["article_id"] for m in mappings]
    if article_ids:
        articles_meta = await db.intelligence_items.find(
            {"id": {"$in": article_ids}},
            {"_id": 0, "id": 1, "source_url": 1, "source": 1,
             "priority_score": 1, "is_cross_border": 1, "regions": 1},
        ).to_list(length=limit)
        meta_map = {a["id"]: a for a in articles_meta}
        for m in mappings:
            meta = meta_map.get(m["article_id"], {})
            m["source_url"] = meta.get("source_url")
            m["source"] = meta.get("source") or m.get("article_source", "")
            m["priority_score"] = meta.get("priority_score")
            m["is_cross_border"] = meta.get("is_cross_border")

    return {
        "faultline_id": fl_id,
        "date": q["date"],
        "total": len(mappings),
        "articles": mappings,
    }
