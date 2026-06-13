import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
from routers.briefs import generate_daily_brief_internal
from routers.pipeline import fetch_news_cycle, retry_unprocessed_cycle

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

def start_scheduler(db):
    # Fetch news every 30 minutes
    scheduler.add_job(
        fetch_news_cycle,
        'interval',
        minutes=30,
        id='news_fetch',
        replace_existing=True,
        args=[db]
    )

    # Retry unprocessed items every 15 minutes
    scheduler.add_job(
        retry_unprocessed_cycle,
        'interval',
        minutes=15,
        id='retry_unprocessed',
        replace_existing=True,
        args=[db]
    )

    # Generate daily brief at 06:00 IST (00:30 UTC)
    ist_tz = timezone('Asia/Kolkata')
    scheduler.add_job(
        generate_daily_brief_internal,
        CronTrigger(hour=6, minute=0, timezone=ist_tz),
        id='daily_brief_0600',
        replace_existing=True,
        args=[db]
    )

    scheduler.start()
    logger.info("APScheduler started with jobs: news_fetch, retry_unprocessed, daily_brief_0600 (06:00 IST)")
