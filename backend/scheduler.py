"""APScheduler nightly price refresh and weekly sets refresh."""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import AsyncSessionLocal
from services import pokewallet
from services.price_cache import get_price

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def nightly_price_refresh() -> None:
    """Refresh prices for all cards in the collection. Runs at 02:00 daily."""
    from sqlalchemy import select
    from models import CollectionEntry

    logger.info("Nightly price refresh starting")
    refreshed = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CollectionEntry.card_api_id).distinct()
        )
        card_ids = [row[0] for row in result.fetchall()]

    if not card_ids:
        logger.info("No cards in collection — skipping price refresh")
        return

    logger.info("Refreshing prices for %d unique cards", len(card_ids))

    for card_id in card_ids:
        if pokewallet.is_hourly_limit_reached():
            logger.warning(
                "Hourly API limit reached mid-refresh — pausing. "
                "Refreshed %d/%d cards. Will resume tomorrow.",
                refreshed,
                len(card_ids),
            )
            break

        async with AsyncSessionLocal() as session:
            prices = await get_price(session, card_id, force_refresh=True)
            if prices:
                refreshed += 1
            else:
                skipped += 1

    logger.info(
        "Nightly price refresh complete — refreshed: %d, skipped: %d, total API calls today: %d",
        refreshed,
        skipped,
        pokewallet.get_calls_today(),
    )


async def weekly_sets_refresh() -> None:
    """Refresh sets list from PokéWallet. Runs Sunday at 03:00."""
    from sqlalchemy import select, delete
    from models import Set

    logger.info("Weekly sets refresh starting")
    raw_sets = await pokewallet.get_sets()
    if not raw_sets:
        logger.warning("Sets refresh returned no data")
        return

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        for raw in raw_sets:
            # API fields: set_id, set_code, name, card_count, language, release_date
            set_id = str(raw.get("set_id") or raw.get("groupId") or raw.get("id") or "")
            if not set_id:
                continue
            existing = await session.get(Set, set_id)
            if existing:
                existing.name = raw.get("name", existing.name)
                existing.set_code = raw.get("set_code") or raw.get("abbreviation") or raw.get("setCode")
                existing.language = raw.get("language")
                existing.release_date = raw.get("release_date") or raw.get("publishedOn") or raw.get("releaseDate")
                existing.card_count = raw.get("card_count") or raw.get("totalCards") or 0
                existing.last_fetched_at = now
            else:
                s = Set(
                    set_id=set_id,
                    set_code=raw.get("set_code") or raw.get("abbreviation") or raw.get("setCode"),
                    name=raw.get("name", ""),
                    language=raw.get("language"),
                    release_date=raw.get("release_date") or raw.get("publishedOn") or raw.get("releaseDate"),
                    card_count=raw.get("card_count") or raw.get("totalCards") or 0,
                    last_fetched_at=now,
                )
                session.add(s)
        await session.commit()

    logger.info("Weekly sets refresh complete — %d sets processed", len(raw_sets))

    # Reset daily counter at midnight
    pokewallet.reset_hourly_counter()


def start_scheduler() -> None:
    scheduler.add_job(
        nightly_price_refresh,
        CronTrigger(hour=2, minute=0),
        id="nightly_price_refresh",
        replace_existing=True,
        name="Nightly price refresh",
    )
    scheduler.add_job(
        weekly_sets_refresh,
        CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="weekly_sets_refresh",
        replace_existing=True,
        name="Weekly sets refresh",
    )
    # Reset hourly counter every hour
    scheduler.add_job(
        pokewallet.reset_hourly_counter,
        CronTrigger(minute=0),
        id="reset_hourly_counter",
        replace_existing=True,
        name="Reset hourly API counter",
    )
    # Reset daily counter at midnight
    scheduler.add_job(
        pokewallet.reset_daily_counter,
        CronTrigger(hour=0, minute=0),
        id="reset_daily_counter",
        replace_existing=True,
        name="Reset daily API counter",
    )
    scheduler.start()
    logger.info(
        "Scheduler started — jobs: %s",
        [job.name for job in scheduler.get_jobs()],
    )


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
