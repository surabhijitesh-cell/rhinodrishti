"""
Faultline Intelligence — API endpoints.

Endpoints:
  POST   /api/faultlines/seed                              — seed/update faultline registry
  GET    /api/faultlines                                   — list all faultlines (optional state filter)
  GET    /api/faultlines/{fl_id}                           — single faultline + latest score
  PATCH  /api/faultlines/{fl_id}                           — update notes / active flag
  GET    /api/faultlines/{fl_id}/history?days=30           — daily score history (trendline)
  GET    /api/faultlines/{fl_id}/articles?date=&limit=     — matched articles + rationale
  GET    /api/faultlines/warnings                          — active un-ack'd alerts (warning banner)
  POST   /api/faultlines/warnings/{alert_id}/ack           — acknowledge an alert
  GET    /api/faultlines/dashboard-summary                 — top stressed faultlines for dashboard pulse strip
  POST   /api/faultlines/run-daily                         — trigger daily pass (manual / debug)
  POST   /api/faultlines/backfill                          — kick off historical backfill (all-time by default)
  GET    /api/faultlines/backfill/status                   — backfill progress
  GET    /api/faultlines/report?year=&month=               — standalone faultline-only PDF report

Reuses:
  - faultline_seed.seed_faultlines for registry seed
  - faultline_engine.run_daily_faultline_pass / run_backfill for compute
  - shared.db (Motor) — schemaless collections: faultlines, faultline_scores,
    faultline_mappings, faultline_alerts, faultline_backfill_status
"""
import asyncio
import io
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from shared import db, logger
from faultline_seed import seed_faultlines, FAULTLINES, STATE_TO_REGIONS
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
alerts_col = db.faultline_alerts
backfill_status_col = db.faultline_backfill_status


# ── Models ────────────────────────────────────────────────────────────────────
class FaultlinePatch(BaseModel):
    active: Optional[bool] = None
    notes: Optional[str] = None
    manual_review_required: Optional[bool] = None


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


# ── Seed ──────────────────────────────────────────────────────────────────────
@router.post("/faultlines/seed")
async def seed_faultline_registry():
    """Seed (or refresh) the faultline registry from faultline_seed.FAULTLINES. Idempotent."""
    result = await seed_faultlines(db)
    return {"status": "ok", **result}


# ── List + detail ─────────────────────────────────────────────────────────────
@router.get("/faultlines")
async def list_faultlines(
    state: Optional[str] = Query(None, description="Filter by state"),
    active_only: bool = Query(True),
    include_score: bool = Query(True),
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


@router.get("/faultlines/dashboard-summary")
async def dashboard_summary(top_n: int = Query(5, ge=1, le=20)):
    """
    Top stressed faultlines (highest current score) for dashboard pulse strip.
    Also returns counts per level.
    """
    # Get most recent date per faultline
    latest_date_cursor = scores_col.find({}, {"date": 1}).sort("date", -1).limit(1)
    latest = [d async for d in latest_date_cursor]
    if not latest:
        return {"top_stressed": [], "level_counts": {}, "as_of": None}

    as_of = latest[0]["date"]
    cursor = scores_col.find({"date": as_of}, {"_id": 0}).sort("score", -1)
    snapshots = [s async for s in cursor]

    level_counts: dict[str, int] = {}
    for s in snapshots:
        lvl = s.get("level") or "STABLE"
        level_counts[lvl] = level_counts.get(lvl, 0) + 1

    return {
        "as_of": as_of,
        "top_stressed": snapshots[:top_n],
        "level_counts": level_counts,
        "total_faultlines": len(snapshots),
    }


@router.get("/faultlines/{fl_id}")
async def get_faultline(fl_id: str):
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
async def update_faultline(fl_id: str, patch: FaultlinePatch):
    """Update notes / active / manual_review_required flags."""
    update_doc: dict = {}
    if patch.active is not None:
        update_doc["active"] = patch.active
    if patch.notes is not None:
        update_doc["notes"] = patch.notes[:5000]
    if patch.manual_review_required is not None:
        update_doc["manual_review_required"] = patch.manual_review_required

    if not update_doc:
        raise HTTPException(400, "No fields to update")

    update_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await faultlines_col.update_one({"id": fl_id}, {"$set": update_doc})
    if result.matched_count == 0:
        raise HTTPException(404, f"Faultline '{fl_id}' not found")
    return {"status": "ok", "updated_fields": list(update_doc.keys())}


@router.get("/faultlines/{fl_id}/history")
async def get_faultline_history(
    fl_id: str,
    days: int = Query(30, ge=1, le=730),
):
    """Daily score history for trendline chart."""
    fl = await faultlines_col.find_one({"id": fl_id}, {"_id": 0, "name": 1, "state": 1})
    if not fl:
        raise HTTPException(404, f"Faultline '{fl_id}' not found")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    cursor = scores_col.find(
        {"faultline_id": fl_id, "date": {"$gte": cutoff}},
        {"_id": 0, "date": 1, "score": 1, "level": 1, "n_articles": 1,
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


# ── Warnings (alerts) ─────────────────────────────────────────────────────────
@router.get("/faultlines/warnings")
async def get_active_warnings(limit: int = Query(20, ge=1, le=100)):
    """All active un-ack'd faultline alerts. Powers dashboard warning banner."""
    cursor = alerts_col.find(
        {"acknowledged": {"$ne": True}},
        {"_id": 0},
    ).sort("created_at", -1).limit(limit * 2)  # extra slack for expiry filtering
    alerts = [a async for a in cursor]

    active = [a for a in alerts if await _is_alert_active(a)]
    return {"total": len(active), "warnings": active[:limit]}


@router.post("/faultlines/warnings/{alert_id}/ack")
async def acknowledge_warning(alert_id: str, acknowledged_by: str = "analyst"):
    """Mark an alert as acknowledged (removes from warning banner)."""
    result = await alerts_col.update_one(
        {"id": alert_id, "acknowledged": {"$ne": True}},
        {"$set": {
            "acknowledged": True,
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
            "acknowledged_by": acknowledged_by,
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Alert not found or already acknowledged")
    return {"status": "ok"}


# ── Generation triggers ───────────────────────────────────────────────────────
@router.post("/faultlines/run-daily")
async def trigger_daily_pass(
    background_tasks: BackgroundTasks,
    target_date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to today"),
):
    """Manually trigger the daily faultline scoring pass (debug / catch-up)."""
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
):
    """
    Kick off historical backfill. Long-running (minutes to hours).
    Re-running same range overwrites existing scores.
    """
    # Mark status
    job_id = f"backfill_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    await backfill_status_col.insert_one({
        "job_id": job_id,
        "status": "running",
        "start_date": start_date,
        "end_date": end_date,
        "started_at": datetime.now(timezone.utc).isoformat(),
    })

    async def _bg():
        try:
            result = await run_backfill(db, start_date=start_date, end_date=end_date)
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
async def backfill_status():
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
