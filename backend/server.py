from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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

# Import scheduler functions
from routers.pipeline import (
    fetch_and_process_news, fetch_grassroots_sources,
    fetch_established_sources, analyze_unprocessed_items,
    run_embedding_backfill,
)
from routers.briefs import generate_scheduled_daily_brief


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
    await initialize_sources()
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
        scheduler.start()
        logger.info("Scheduler: grassroots/60min, standard/30min, established/12hr, retry/15min, brief/0600 IST, embeddings/6hr")
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
