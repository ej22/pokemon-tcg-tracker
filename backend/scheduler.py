"""APScheduler nightly price refresh and weekly sets refresh."""
import asyncio
import logging
import random

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import AsyncSessionLocal
from services import pokewallet
from services.price_cache import get_price

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# Max number of CardMarket scrapes per nightly run (prevents hammering CM at scale)
_SCRAPE_NIGHT_CAP = 60


async def nightly_price_refresh() -> None:
    """Refresh prices for all cards in the collection. Runs at 02:00 daily."""
    from sqlalchemy import select
    from models import CollectionEntry, Card
    from routers.settings import get_pricing_mode

    async with AsyncSessionLocal() as session:
        pricing_mode = await get_pricing_mode(session)
    if pricing_mode != "full":
        logger.info("Nightly price refresh skipped — pricing is disabled (collection-only mode)")
        return

    logger.info("Nightly price refresh starting")

    # ── Phase 1: PokéWallet cards ────────────────────────────────────
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CollectionEntry.card_api_id).distinct()
        )
        all_ids = [row[0] for row in result.fetchall()]

    if not all_ids:
        logger.info("No cards in collection — skipping price refresh")
        return

    # Split into PokéWallet vs PriceCharting-scraped
    pw_ids: list[str] = []
    scrape_ids: list[str] = []

    async with AsyncSessionLocal() as session:
        for card_id in all_ids:
            card = await session.get(Card, card_id)
            if card and card.source == "pricecharting_scrape":
                scrape_ids.append(card_id)
            else:
                pw_ids.append(card_id)

    # Refresh PokéWallet cards
    refreshed = 0
    skipped = 0
    logger.info("Refreshing PokéWallet prices for %d cards", len(pw_ids))

    for card_id in pw_ids:
        if pokewallet.is_hourly_limit_reached():
            logger.warning(
                "Hourly API limit reached mid-refresh — pausing. "
                "Refreshed %d/%d PokéWallet cards. Will resume tomorrow.",
                refreshed,
                len(pw_ids),
            )
            break

        async with AsyncSessionLocal() as session:
            prices = await get_price(session, card_id, force_refresh=True)
            if prices:
                refreshed += 1
            else:
                skipped += 1

    logger.info(
        "PokéWallet refresh complete — refreshed: %d, skipped: %d, total API calls today: %d",
        refreshed,
        skipped,
        pokewallet.get_calls_today(),
    )

    # ── Phase 2: CardMarket scraped cards ────────────────────────────
    if not scrape_ids:
        logger.info("No CardMarket-scraped cards in collection — skipping scrape pass")
        return

    capped = scrape_ids[:_SCRAPE_NIGHT_CAP]
    if len(scrape_ids) > _SCRAPE_NIGHT_CAP:
        logger.warning(
            "Scrape cap reached: %d scraped cards total, refreshing first %d only",
            len(scrape_ids),
            _SCRAPE_NIGHT_CAP,
        )

    scrape_ok = 0
    scrape_fail = 0
    logger.info("Refreshing PriceCharting scraped prices for %d cards", len(capped))

    from services.pricecharting_scraper import ScrapeError
    from services.price_cache import scrape_and_store
    from services.currency import refresh_rate

    # Refresh exchange rate once before the scrape pass
    await refresh_rate()

    for card_id in capped:
        async with AsyncSessionLocal() as session:
            card = await session.get(Card, card_id)
            if not card or not card.source_url:
                continue
            try:
                await scrape_and_store(session, card.source_url, force_refresh=True)
                scrape_ok += 1
            except ScrapeError as e:
                logger.warning("Nightly scrape failed for %s: %s", card_id, e)
                scrape_fail += 1

        # Throttle: wait between 2 and 4 seconds between requests
        await asyncio.sleep(random.uniform(2.0, 4.0))

    logger.info(
        "PriceCharting scrape pass complete — ok: %d, failed: %d",
        scrape_ok,
        scrape_fail,
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
