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
@router.post("/priority-areas/seed")
async def seed_priority_area_registry(
    current_user: dict = Depends(get_current_user),
):
    """Seed PAOIs + tag faultlines with priority_area_ids. Idempotent.
    Run AFTER /faultlines/seed (it tags existing faultlines)."""
    _require_analyst_or_admin(current_user)
    result = await seed_priority_areas(db)
    return {"status": "ok", **result}


@router.get("/priority-areas")
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


# ── Standalone faultline PDF report ───────────────────────────────────────────
@router.get("/faultlines/report")
async def faultline_pdf_report(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    current_user: dict = Depends(get_current_user),
):
    """
    Standalone faultline-only PDF report for a calendar month.
    Aggregates all faultline_scores for the month, groups by state, identifies
    rising / declining faultlines, includes manual review advisory.
    """
    from fpdf import FPDF
    from collections import defaultdict

    # Window
    start = datetime(year, month, 1, tzinfo=timezone.utc).date()
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc).date()
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc).date()

    # Load scores in window
    cursor = scores_col.find(
        {"date": {"$gte": start.isoformat(), "$lt": end.isoformat()}},
        {"_id": 0},
    ).sort([("faultline_id", 1), ("date", 1)])
    all_scores = [s async for s in cursor]

    if not all_scores:
        raise HTTPException(404, f"No faultline data for {year}-{month:02d}")

    # Group by faultline → compute first/last/peak
    by_fl: dict[str, list] = defaultdict(list)
    for s in all_scores:
        by_fl[s["faultline_id"]].append(s)

    fl_summaries = []
    for fl_id, series in by_fl.items():
        series = sorted(series, key=lambda x: x["date"])
        first = series[0]["score"]
        last = series[-1]["score"]
        peak = max(s["score"] for s in series)
        avg = sum(s["score"] for s in series) / len(series)
        fl_summaries.append({
            "faultline_id": fl_id,
            "faultline_name": series[-1]["faultline_name"],
            "state": series[-1]["state"],
            "first_score": first,
            "last_score": last,
            "peak_score": peak,
            "avg_score": avg,
            "delta": last - first,
            "days_observed": len(series),
            "level": series[-1]["level"],
        })

    # Group by state
    by_state: dict[str, list] = defaultdict(list)
    for summary in fl_summaries:
        by_state[summary["state"]].append(summary)

    # Build PDF (clean ASCII-safe to avoid Helvetica unicode issues)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Faultline Intelligence Report - {start.strftime('%B %Y')}", ln=True)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Period: {start.isoformat()} to {(end - timedelta(days=1)).isoformat()}", ln=True)
    pdf.cell(0, 6, f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", ln=True)
    pdf.ln(4)

    # Overall summary
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Executive Summary", ln=True)
    pdf.set_font("Helvetica", "", 10)
    rising = [s for s in fl_summaries if s["delta"] >= 10]
    declining = [s for s in fl_summaries if s["delta"] <= -10]
    critical = [s for s in fl_summaries if s["last_score"] >= 75]
    pdf.multi_cell(0, 5,
        f"Faultlines monitored: {len(fl_summaries)} across {len(by_state)} states.\n"
        f"Currently CRITICAL: {len(critical)}.\n"
        f"Rising (delta >= +10): {len(rising)}.\n"
        f"Declining (delta <= -10): {len(declining)}."
    )
    pdf.ln(3)

    # Per state
    for state in sorted(by_state.keys()):
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 7, state, ln=True)
        pdf.set_font("Helvetica", "", 9)

        state_fls = sorted(by_state[state], key=lambda x: -x["last_score"])
        for fl in state_fls:
            arrow = "UP" if fl["delta"] > 2 else ("DOWN" if fl["delta"] < -2 else "FLAT")
            line = (f"  {fl['faultline_name'][:60]:60s} "
                    f"{fl['last_score']:5.1f}  ({fl['level']})  "
                    f"{arrow} {fl['delta']:+5.1f}  "
                    f"peak {fl['peak_score']:5.1f}")
            # ASCII-safe
            line = line.encode("ascii", "ignore").decode("ascii")
            pdf.cell(0, 5, line, ln=True)
        pdf.ln(2)

    # Manual review advisory
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Manual Review Advisory", ln=True)
    pdf.set_font("Helvetica", "", 10)
    advisory = (
        "For faultlines with rising scores, weak signals, or rapidly changing trajectories, "
        "supplement automated analysis with manual review of:\n"
        "  - Local news cycles in regional languages (Assamese, Bengali, Manipuri, Mizo, Naga)\n"
        "  - Narrative spikes on Twitter/X, YouTube, and Telegram channels\n"
        "  - Influencer amplification patterns across local political pages\n"
        "  - Cross-posting patterns linking different platforms (text-to-image-to-video)\n"
        "  - Repeated narrative claims that align with foreign-influence indicators\n\n"
        "Specifically inspect for the rising faultlines identified above."
    )
    pdf.multi_cell(0, 5, advisory.encode("ascii", "ignore").decode("ascii"))

    if rising:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, "Priority faultlines for manual review:", ln=True)
        pdf.set_font("Helvetica", "", 9)
        for fl in sorted(rising, key=lambda x: -x["delta"])[:10]:
            line = f"  - [{fl['state']}] {fl['faultline_name'][:70]} (now {fl['last_score']:.0f}, +{fl['delta']:.0f})"
            line = line.encode("ascii", "ignore").decode("ascii")
            pdf.cell(0, 5, line, ln=True)

    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    filename = f"faultline_report_{year}_{month:02d}.pdf"
    return StreamingResponse(
        buf,
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

    cursor = mappings_col.find(q, {"_id": 0}).sort("impact_score", -1).limit(limit)
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
