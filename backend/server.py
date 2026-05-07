from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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


app = FastAPI(title="Rhino Drishti API")


# ============================================================
# Mount All Routers
# ============================================================
app.include_router(intelligence_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(briefs_router, prefix="/api")
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


# ============================================================
# Root Endpoint
# ============================================================
@app.get("/api/")
async def root():
    return {"message": "Rhino Drishti API - Intelligence Aggregation Platform"}


# ============================================================
# WebSocket Endpoint
# ============================================================
@app.websocket("/api/ws/intelligence")
async def websocket_intelligence(websocket: WebSocket):
    await ws_manager.connect(websocket)
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
    for source in RSS_SOURCES:
        await sources_col.update_one(
            {"url": source["url"]},
            {"$set": {**source, "id": str(uuid.uuid4())}},
            upsert=True
        )
    count = await sources_col.count_documents({})
    logger.info(f"RSS sources synced: {count} total ({len(RSS_SOURCES)} configured)")


@app.on_event("startup")
async def startup():
    # Auto-seed admin user if no users exist
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

    await initialize_sources()
    await seed_firecrawl_defaults(db)
    await seed_twitter_defaults(db)
    await seed_youtube_defaults(db)
    await seed_telegram_defaults(db)
    item_count = await intelligence_col.count_documents({})
    if item_count == 0:
        logger.info("Empty database - triggering initial fetch...")
        asyncio.create_task(fetch_and_process_news())
    else:
        logger.info(f"Database has {item_count} items. Skipping startup fetch (scheduler will handle next cycle).")
        unprocessed = await intelligence_col.count_documents({"processed": False})
        if unprocessed > 0:
            logger.info(f"{unprocessed} unprocessed items found - triggering retry...")
            asyncio.create_task(analyze_unprocessed_items())

    # One-time repair: un-archive any items younger than 7 days that were
    # incorrectly archived before the freshness guard was added to fading_engine.
    try:
        from datetime import datetime, timezone, timedelta
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        repair_result = await intelligence_col.update_many(
            {"is_archived": True, "published_at": {"$gte": seven_days_ago}, "pinned": {"$ne": True}},
            {"$set": {"is_archived": False, "visibility_band": "fading"}},
        )
        if repair_result.modified_count:
            logger.info(f"Startup repair: un-archived {repair_result.modified_count} fresh items (< 7 days old)")
    except Exception as e:
        logger.warning(f"Startup archive repair failed: {e}")

    # One-time repair: re-assign cluster primaries using recency-first logic.
    # Previously pick_primary sorted by summary length, causing old items to stay as
    # cluster heads while fresh articles were hidden.  This re-assigns primaries
    # within all clusters formed in the last 30 days.
    try:
        from fusion_engine import repair_cluster_primaries
        repair_stats = await repair_cluster_primaries(db)
        if repair_stats.get("primaries_reassigned", 0) > 0:
            logger.info(
                f"Startup cluster repair: reassigned {repair_stats['primaries_reassigned']} "
                f"cluster primaries to most-recent items (checked {repair_stats.get('clusters_checked', 0)} clusters)"
            )
    except Exception as e:
        logger.warning(f"Startup cluster primary repair failed: {e}")

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

        # Firecrawl jobs
        async def _fetch_web_sources():
            try:
                n = await fetch_web_sources(db)
                logger.info(f"Firecrawl web sources: {n} new items")
            except Exception as e:
                logger.warning(f"Firecrawl web sources job failed: {e}")

        async def _run_keyword_searches():
            try:
                n = await run_keyword_searches(db)
                logger.info(f"Firecrawl keyword searches: {n} new items")
            except Exception as e:
                logger.warning(f"Firecrawl keyword search job failed: {e}")

        scheduler.add_job(_fetch_web_sources,    'interval', hours=3,   id='firecrawl_web_sources')
        scheduler.add_job(_run_keyword_searches, 'interval', hours=6,   id='firecrawl_searches')

        # Social media jobs
        async def _fetch_twitter():
            try:
                a = await fetch_twitter_accounts(db)
                s = await fetch_twitter_searches(db)
                logger.info(f"Twitter: {a} account tweets, {s} search tweets")
            except Exception as e:
                logger.warning(f"Twitter job failed: {e}")

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

        scheduler.add_job(_fetch_twitter,  'interval', hours=2,  id='twitter_fetch')
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

        scheduler.start()
        logger.info("Scheduler: grassroots/60min, standard/30min, established/12hr, retry/15min, brief/0600 IST, embeddings/6hr, fusion/30min, firecrawl-web/3hr, firecrawl-search/6hr, twitter/2hr, youtube/4hr, telegram/1hr, fading/1hr")
    except Exception as e:
        logger.warning(f"Scheduler setup failed: {e}")


@app.on_event("shutdown")
async def shutdown():
    client.close()


# ============================================================
# CORS
# ============================================================
cors_origins_str = os.environ.get('CORS_ORIGINS', '*')
if cors_origins_str.strip() == '*':
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
else:
    origins = [o.strip() for o in cors_origins_str.split(',') if o.strip()]
    # Always include common deployment domains
    for domain in ["https://rhinodrishti.vercel.app", "https://www.rhinodrishti.vercel.app"]:
        if domain not in origins:
            origins.append(domain)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
