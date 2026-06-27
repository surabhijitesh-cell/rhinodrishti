from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from datetime import datetime, timezone
from starlette.middleware.cors import CORSMiddleware
import os
import uuid
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from shared import (
    client, db, intelligence_col, sources_col,
    ws_manager, logger,
)

# Import routers
from routers.intelligence import router as intelligence_router
from routers.settings import router as settings_router
from routers.briefs import router as briefs_router
from routers.trends import router as trends_router
from routers.analytics import router as analytics_router
from routers.brief_monthly import router as brief_monthly_router
from routers.pipeline import router as pipeline_router
from routers.documents import router as documents_router
from routers.knowledge_graph_routes import router as kg_router
from routers.keywords_routes import router as keywords_router
from routers.sources import router as sources_router
from routers.feedback import router as feedback_router
from routers.training import router as training_router
from routers.cross_border import router as cross_border_router
from routers.auth import router as auth_router
from routers.app_updates import router as app_updates_router
from routers.reports import router as reports_router
from routers.web_sources import router as web_sources_router
from routers.social_media import router as social_media_router
from routers.admin import router as admin_router
from routers.relationships import router as relationships_router
from routers.brief_fortnightly import router as brief_fortnightly_router
from routers.faultlines import router as faultlines_router
from routers.watchlist import router as watchlist_router
from routers.notifications import router as notifications_router
from routers.flags import router as flags_router

# Import scheduler functions
from routers.pipeline import (
    fetch_and_process_news, fetch_grassroots_sources,
    fetch_established_sources, analyze_unprocessed_items,
    run_embedding_backfill,
)
from routers.briefs import generate_scheduled_daily_brief
from fusion_engine import run_batch_fusion
from firecrawl_fetcher import fetch_web_sources, run_keyword_searches, seed_firecrawl_defaults
from twitter_fetcher import fetch_twitter_accounts, fetch_twitter_searches, seed_twitter_defaults
from youtube_fetcher import fetch_youtube_channels, fetch_youtube_searches, seed_youtube_defaults
from telegram_fetcher import fetch_telegram_channels, seed_telegram_defaults
from fading_engine import run_fading_pass, delete_expired_low_severity
from faultline_engine import run_daily_faultline_pass, run_incremental_faultline_pass


app = FastAPI(title="Rhino Drishti API")


# ============================================================
# Mount All Routers
# ============================================================
app.include_router(intelligence_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(briefs_router, prefix="/api")
app.include_router(trends_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(brief_monthly_router, prefix="/api")
app.include_router(pipeline_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(kg_router, prefix="/api")
app.include_router(keywords_router, prefix="/api")
app.include_router(sources_router, prefix="/api")
app.include_router(feedback_router, prefix="/api")
app.include_router(training_router, prefix="/api")
app.include_router(cross_border_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(app_updates_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(web_sources_router, prefix="/api")
app.include_router(social_media_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(relationships_router, prefix="/api")
app.include_router(brief_fortnightly_router, prefix="/api")
app.include_router(faultlines_router, prefix="/api")
app.include_router(watchlist_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(flags_router, prefix="/api")


# ============================================================
# Root Endpoint
# ============================================================
@app.get("/api/")
async def root():
    return {"message": "Rhino Drishti API - Intelligence Aggregation Platform"}


@app.get("/api/health")
async def health():
    """Lightweight keep-alive endpoint — no DB query, no auth. Pinged every 10 min by GitHub Actions to prevent Render cold-starts."""
    return {"status": "ok"}


# ============================================================
# WebSocket Endpoint
# ============================================================
@app.websocket("/api/ws/intelligence")
async def websocket_intelligence(websocket: WebSocket, token: str = Query(default=None)):
    user_id = None
    if token:
        try:
            from utils.auth import verify_token
            payload = verify_token(token)
            user_id = payload.get("sub")
        except Exception:
            pass  # anonymous WS still connects; targeted delivery won't work
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# ============================================================
# Startup & Shutdown
# ============================================================
async def initialize_sources():
    from rss_fetcher import RSS_SOURCES
    try:
        for source in RSS_SOURCES:
            await sources_col.update_one(
                {"url": source["url"]},
                {"$set": {**source, "id": str(uuid.uuid4())}},
                upsert=True
            )
        count = await sources_col.count_documents({})
        logger.info(f"RSS sources synced: {count} total ({len(RSS_SOURCES)} configured)")
    except Exception as e:
        logger.warning(f"initialize_sources failed (non-fatal): {e}")


async def _deferred_init(item_count: int):
    """
    Heavy startup work deferred to a background task so the startup
    handler returns fast and uvicorn can bind its port within Render's
    port-scan window (~5 s).  All operations here are non-critical for
    the first request.
    """
    # Source seeding (upserts — safe to run repeatedly)
    try:
        await seed_firecrawl_defaults(db)
        await seed_twitter_defaults(db)
        await seed_youtube_defaults(db)
        await seed_telegram_defaults(db)
    except Exception as e:
        logger.warning(f"Deferred seed failed: {e}")

    # Priority Areas of Interest (PAOI) seed — idempotent upsert + faultline tagging.
    # Required for Faultline Analysis Report PDF page 2 + monthly brief PAOI sections.
    try:
        from priority_areas_seed import seed_priority_areas
        paoi_result = await seed_priority_areas(db)
        logger.info(f"PAOI registry seeded: {paoi_result}")
    except Exception as e:
        logger.warning(f"PAOI seed failed: {e}")

    # App update history seeding — inserts any missing versions, skips existing
    try:
        from seed_updates import UPDATES
        inserted = 0
        for u in UPDATES:
            existing = await db.app_updates.find_one({"version": u["version"]})
            if not existing:
                import uuid as _uuid
                await db.app_updates.insert_one({"id": str(_uuid.uuid4()), **u})
                inserted += 1
        if inserted:
            logger.info(f"App updates seeded: {inserted} new version(s) added")
    except Exception as e:
        logger.warning(f"App updates seed failed: {e}")

    # Initial fetch only when DB is truly empty
    if item_count == 0:
        logger.info("Empty database — triggering initial fetch…")
        await fetch_and_process_news()

    # One-time stage-0 filter repair: items that were incorrectly rejected by the
    # old hard_filter (empty source_region fell through to no_match instead of
    # fail-open RULE 7). Reset them to unprocessed so the fixed filter re-evaluates.
    try:
        r = await intelligence_col.update_many(
            {"tags": "stage0_filtered"},
            {
                "$set": {"processed": False, "severity": "low", "filter_reason": None},
                "$pull": {"tags": "stage0_filtered"},
            },
        )
        if r.modified_count:
            logger.info(f"Startup repair: reset {r.modified_count} stage0-filtered items → unprocessed")
            from shared import invalidate_stats_cache
            invalidate_stats_cache()
    except Exception as e:
        logger.warning(f"Stage-0 repair failed: {e}")

    # One-time archive repair (update_many on 23k docs can take 5-10 s)
    try:
        from datetime import timedelta
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        r = await intelligence_col.update_many(
            {"is_archived": True, "published_at": {"$gte": seven_days_ago}, "pinned": {"$ne": True}},
            {"$set": {"is_archived": False, "visibility_band": "fading"}},
        )
        if r.modified_count:
            logger.info(f"Deferred repair: un-archived {r.modified_count} fresh items (< 7 days old)")
    except Exception as e:
        logger.warning(f"Deferred archive repair failed: {e}")

    # One-time cluster-primary repair (aggregates 3000+ clusters — slow)
    try:
        from fusion_engine import repair_cluster_primaries
        stats = await repair_cluster_primaries(db)
        if stats.get("primaries_reassigned", 0) > 0:
            logger.info(f"Deferred cluster repair: reassigned {stats['primaries_reassigned']} primaries "
                        f"(checked {stats.get('clusters_checked', 0)} clusters)")
    except Exception as e:
        logger.warning(f"Deferred cluster repair failed: {e}")

    # Severity/priority_score consistency repair (idempotent — no-op after first run)
    # Old code stored AI's raw severity field; AI contradicted its own score frequently.
    # New code derives severity from priority_score, but existing DB items need backfill.
    try:
        from routers.intelligence import repair_severity_mismatch
        result = await repair_severity_mismatch()
        if result["fixed_total"]:
            logger.info(
                f"Startup severity repair: {result['fixed_total']} items corrected "
                f"(critical+{result['fixed_critical']}, high+{result['fixed_high']}, "
                f"medium+{result['fixed_medium']}, low+{result['fixed_low']})"
            )
    except Exception as e:
        logger.warning(f"Startup severity repair failed: {e}")


@app.on_event("startup")
async def startup():
    """
    KEEP THIS FAST — Render kills the process if the port is not open
    within ~5 s of startup.  Heavy work goes into _deferred_init().
    """
    # Notification collection indexes (idempotent)
    try:
        await db.notification_recipients.create_index([("user_id", 1), ("is_read", 1), ("created_at", -1)])
        await db.notification_recipients.create_index([("notification_id", 1), ("user_id", 1)], unique=True)
        await db.push_subscriptions.create_index("endpoint", unique=True)
        await db.push_subscriptions.create_index([("user_id", 1), ("active", 1)])
        await db.user_notification_prefs.create_index("user_id", unique=True)
        await db.news_flags.create_index([("flagged_by", 1), ("article_id", 1), ("created_at", -1)])
        await db.state_severity_snapshots.create_index("state", unique=True)
    except Exception as idx_err:
        logger.warning(f"Notification index setup failed (non-fatal): {idx_err}")

    # Admin user seed (one count + maybe one insert — <100 ms)
    user_count = await db.users.count_documents({})
    if user_count == 0:
        from utils.auth import hash_password
        admin_doc = {
            "id": "admin-001",
            "username": "admin",
            "email": "admin@rhinodrishti.local",
            "password_hash": hash_password("Admin@2026!"),
            "name": "System Administrator",
            "role": "admin",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": None,
        }
        await db.users.insert_one(admin_doc)
        logger.info("Auto-seeded admin user (admin / Admin@2026!) — change password after first login")

    # RSS source sync (upserts ~95 docs — <2 s, needed before scheduler fires)
    await initialize_sources()

    # DB state log (two counts — <200 ms)
    item_count = await intelligence_col.count_documents({})
    unprocessed  = await intelligence_col.count_documents({"processed": False})
    logger.info(f"Database: {item_count} items ({unprocessed} unprocessed). Scheduler handles cycles.")

    # Defer all slow work so startup returns and port binds immediately
    asyncio.create_task(_deferred_init(item_count))

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        scheduler = AsyncIOScheduler()
        scheduler.add_job(fetch_grassroots_sources, 'interval', minutes=60, id='grassroots_fetch')
        scheduler.add_job(fetch_and_process_news, 'interval', minutes=30, id='news_fetch')
        scheduler.add_job(fetch_established_sources, 'interval', hours=12, id='established_fetch')
        scheduler.add_job(analyze_unprocessed_items, 'interval', minutes=15, id='retry_unprocessed')
        scheduler.add_job(
            generate_scheduled_daily_brief,
            CronTrigger(hour=0, minute=30, timezone='UTC'),
            id='daily_brief_0600',
            misfire_grace_time=3600
        )
        scheduler.add_job(run_embedding_backfill, 'interval', hours=6, id='embedding_backfill')
        async def _run_batch_fusion():
            try:
                stats = await run_batch_fusion(db)
                logger.info(f"Scheduled batch fusion: {stats}")
            except Exception as e:
                logger.warning(f"Scheduled batch fusion failed: {e}")
        scheduler.add_job(_run_batch_fusion, 'interval', minutes=30, id='batch_fusion')

        # OpenRouter credit monitor — warns at $2 (amber) and $0.50 (red)
        async def _check_openrouter_credits():
            try:
                import os, httpx
                key = os.environ.get("OPENROUTER_API_KEY", "")
                if not key:
                    return
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.get(
                        "https://openrouter.ai/api/v1/auth/key",
                        headers={"Authorization": f"Bearer {key}"},
                    )
                if r.status_code != 200:
                    return
                data = r.json().get("data", {})
                limit = data.get("limit")
                usage = data.get("usage", 0)
                # limit_remaining is the authoritative remaining balance field.
                # Fall back to limit-usage when not present; skip only when truly unlimited.
                limit_remaining = data.get("limit_remaining")
                logger.info(f"OpenRouter auth/key → limit={limit} usage={usage} limit_remaining={limit_remaining}")
                if limit_remaining is not None:
                    remaining = round(limit_remaining, 4)
                elif limit is not None:
                    remaining = round(limit - usage, 4)
                else:
                    # Prepaid account with no monthly cap — cannot determine balance from auth/key.
                    # Fall back to exhaustion flag set by 402 errors during actual LLM calls.
                    from llm_client import set_credit_warning, get_credit_warning, is_openrouter_exhausted
                    if is_openrouter_exhausted():
                        set_credit_warning("critical", None)
                        logger.warning("OpenRouter credits: exhaustion flag set (402 errors) — marking critical")
                    return
                from llm_client import set_credit_warning, get_credit_warning
                prev_level = get_credit_warning()["level"]
                if remaining <= 0.50:
                    new_level = "critical"
                elif remaining <= 2.00:
                    new_level = "low"
                else:
                    new_level = "ok"
                set_credit_warning(new_level, remaining)
                if new_level != "ok":
                    logger.warning(f"OpenRouter credits {new_level.upper()}: ${remaining:.4f} remaining")
                # Notify users when level worsens (ok→low, ok→critical, low→critical)
                _severity = {"ok": 0, "low": 1, "critical": 2}
                if _severity.get(new_level, 0) > _severity.get(prev_level, 0):
                    try:
                        from utils.notifications import create_and_dispatch_notification, resolve_system_notification_recipients
                        recipients = await resolve_system_notification_recipients(db, "SYSTEM_ALERT")
                        if recipients:
                            emoji = "🔴" if new_level == "critical" else "🟡"
                            await create_and_dispatch_notification(
                                notif_type="SYSTEM_ALERT",
                                title=f"{emoji} OpenRouter credits {new_level.upper()}: ${remaining:.2f} remaining",
                                body="LLM synthesis will fail when credits reach $0. Top up at openrouter.ai/credits.",
                                payload={"level": new_level, "remaining_usd": remaining},
                                deep_link="/admin",
                                source_type="system",
                                source_id="credit_monitor",
                                created_by=None,
                                recipient_user_ids=recipients,
                            )
                    except Exception as ne:
                        logger.warning(f"Credit alert notification failed: {ne}")
            except Exception as e:
                logger.warning(f"Credit monitor check failed: {e}")

        scheduler.add_job(_check_openrouter_credits, 'interval', minutes=30, id='credit_monitor')
        # Run once immediately so the warning level is set before the first 30-min tick.
        asyncio.create_task(_check_openrouter_credits())

        # Firecrawl jobs — DISABLED (insufficient credits; re-enable when plan upgraded)
        # async def _fetch_web_sources():
        #     try:
        #         n = await fetch_web_sources(db)
        #         logger.info(f"Firecrawl web sources: {n} new items")
        #     except Exception as e:
        #         logger.warning(f"Firecrawl web sources job failed: {e}")
        #
        # async def _run_keyword_searches():
        #     try:
        #         n = await run_keyword_searches(db)
        #         logger.info(f"Firecrawl keyword searches: {n} new items")
        #     except Exception as e:
        #         logger.warning(f"Firecrawl keyword search job failed: {e}")
        #
        # scheduler.add_job(_fetch_web_sources,    'interval', hours=3,   id='firecrawl_web_sources')
        # scheduler.add_job(_run_keyword_searches, 'interval', hours=6,   id='firecrawl_searches')
        logger.info("Firecrawl scheduled jobs disabled — re-enable in server.py when credits restored")

        # Social media jobs
        # Twitter — DISABLED (API costs; re-enable when needed)
        # async def _fetch_twitter():
        #     try:
        #         a = await fetch_twitter_accounts(db)
        #         s = await fetch_twitter_searches(db)
        #         logger.info(f"Twitter: {a} account tweets, {s} search tweets")
        #     except Exception as e:
        #         logger.warning(f"Twitter job failed: {e}")

        async def _fetch_youtube():
            try:
                c = await fetch_youtube_channels(db)
                s = await fetch_youtube_searches(db)
                logger.info(f"YouTube: {c} channel videos, {s} search videos")
            except Exception as e:
                logger.warning(f"YouTube job failed: {e}")

        async def _fetch_telegram():
            try:
                n = await fetch_telegram_channels(db)
                logger.info(f"Telegram: {n} new messages")
            except Exception as e:
                logger.warning(f"Telegram job failed: {e}")

        # scheduler.add_job(_fetch_twitter,  'interval', hours=2,  id='twitter_fetch')  # DISABLED
        scheduler.add_job(_fetch_youtube,  'interval', hours=4,  id='youtube_fetch')
        scheduler.add_job(_fetch_telegram, 'interval', hours=1,  id='telegram_fetch')

        # Fading engine — recomputes visibility_score every hour
        async def _run_fading_pass():
            try:
                stats = await run_fading_pass()
                logger.info(f"Fading pass: {stats}")
            except Exception as e:
                logger.warning(f"Fading pass failed: {e}")

        scheduler.add_job(_run_fading_pass, 'interval', hours=1, id='fading_pass')

        # Daily low-severity hard-delete (runs at 02:00 IST = 20:30 UTC previous day)
        async def _delete_low_sev():
            try:
                stats = await delete_expired_low_severity()
                logger.info(f"Low-severity cleanup: {stats}")
            except Exception as e:
                logger.warning(f"Low-severity cleanup failed: {e}")

        scheduler.add_job(
            _delete_low_sev,
            CronTrigger(hour=20, minute=30, timezone='UTC'),  # 02:00 IST (UTC+5:30)
            id='low_sev_cleanup',
            misfire_grace_time=3600,
        )

        # Relationship batch — nightly at 03:00 UTC (08:30 IST), after daily brief
        # Rebuilds KG + patterns first so all 5 relationship passes use fresh data.
        async def _run_relationship_batch():
            try:
                from knowledge_graph import build_knowledge_graph
                from pattern_engine import detect_patterns
                await build_knowledge_graph(db)
                await detect_patterns(db)
                from relationship_engine import run_relationship_batch
                summary = await run_relationship_batch()
                logger.info(f"Relationship batch: {summary}")
            except Exception as e:
                logger.warning(f"Relationship batch failed: {e}")

        scheduler.add_job(
            _run_relationship_batch,
            CronTrigger(hour=21, minute=30, timezone='UTC'),  # 03:00 IST (UTC+5:30)
            id='relationship_batch',
            misfire_grace_time=3600,
        )

        # Faultline daily pass — nightly at 22:30 UTC (04:00 IST), after relationships
        # Scores all faultlines for today using last 7d window, applies propagation,
        # emits warning alerts. Idempotent — re-running same day overwrites scores.
        async def _run_faultline_pass():
            try:
                from faultline_seed import FAULTLINES
                # Ensure registry seeded (idempotent — no-op if already current)
                if await db.faultlines.count_documents({}) < len(FAULTLINES):
                    from faultline_seed import seed_faultlines
                    seed_result = await seed_faultlines(db)
                    logger.info(f"Faultline registry seeded: {seed_result}")
                summary = await run_daily_faultline_pass(db)
                logger.info(f"Faultline daily pass: {summary}")
            except Exception as e:
                logger.warning(f"Faultline daily pass failed: {e}")

        # Full LLM pass twice daily: 00:30 UTC (06:00 IST) + 12:30 UTC (18:00 IST)
        scheduler.add_job(
            _run_faultline_pass,
            CronTrigger(hour=0, minute=30, timezone='UTC'),
            id='faultline_daily_pass_morning',
            misfire_grace_time=3600,
        )
        scheduler.add_job(
            _run_faultline_pass,
            CronTrigger(hour=12, minute=30, timezone='UTC'),
            id='faultline_daily_pass_evening',
            misfire_grace_time=3600,
        )

        # Incremental keyword-only pass every 4 hours — keeps article list current
        # between LLM passes without triggering expensive scoring calls.
        async def _run_incremental_faultline_pass():
            try:
                result = await run_incremental_faultline_pass(db)
                logger.info(f"Faultline incremental pass: {result}")
            except Exception as e:
                logger.warning(f"Faultline incremental pass failed: {e}")

        scheduler.add_job(
            _run_incremental_faultline_pass,
            'interval',
            hours=4,
            id='faultline_incremental_pass',
            misfire_grace_time=600,
        )

        async def _strip_old_raw_content():
            try:
                from datetime import timedelta
                cutoff = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%d")
                result = await intelligence_col.update_many(
                    {
                        "published_at": {"$lt": cutoff},
                        "processed": True,
                        "raw_content": {"$exists": True, "$ne": None},
                    },
                    {"$unset": {"raw_content": ""}}
                )
                if result.modified_count:
                    logger.info(f"Storage cleanup: stripped raw_content from {result.modified_count} articles older than 45 days")
            except Exception as e:
                logger.warning(f"raw_content strip job failed: {e}")

        scheduler.add_job(
            _strip_old_raw_content,
            'interval',
            hours=24,
            id='strip_raw_content',
            misfire_grace_time=3600,
        )

        scheduler.start()
        logger.info("Scheduler: grassroots/60min, standard/30min, established/12hr, retry/15min, brief/0600 IST, embeddings/6hr, fusion/30min, youtube/4hr, telegram/1hr, fading/1hr, relationships/nightly, faultlines/0600+1800 IST + incremental/4hr, credit_monitor/30min, strip_raw/24hr [firecrawl+twitter DISABLED]")
    except Exception as e:
        logger.warning(f"Scheduler setup failed: {e}")


@app.on_event("shutdown")
async def shutdown():
    client.close()


# ============================================================
# CORS
# ============================================================
# Allow all origins unconditionally — auth uses JWT tokens in Authorization
# header, not cookies, so allow_credentials=False is safe and allow_origins=["*"]
# covers all Vercel preview URLs, custom domains, and local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
