"""Spy Radar Worker — Railway Service #2.

Standalone APScheduler process that polls spy_targets on interval.
Uses the same env vars as the main bot (Railway shared environment).

Entry point:
    python -m workers.spy_worker
    # or in Procfile: worker: python -m workers.spy_worker
"""
from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def _main():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from supabase import acreate_client

    from config import SUPABASE_URL, SUPABASE_KEY
    import storage.spy_store as spy_store
    from workers.spy_poller import run_spy_poll_cycle

    interval_minutes = int(os.getenv("SPY_CHECK_INTERVAL_MINUTES", "15"))

    client = await acreate_client(SUPABASE_URL, SUPABASE_KEY)
    spy_store.set_client(client)
    logger.info("Supabase client initialized for spy worker.")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        lambda: asyncio.create_task(run_spy_poll_cycle()),
        "interval",
        minutes=interval_minutes,
        id="spy_poll",
    )
    scheduler.start()
    logger.info("Spy Radar worker started. Poll interval: %d min.", interval_minutes)

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Spy worker stopped.")


if __name__ == "__main__":
    asyncio.run(_main())
