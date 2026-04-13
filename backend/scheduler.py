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
    """Refresh prices for all cards in the collection. Runs at 02:00 daily.

    In full mode: refresh every card.
    In collection_only mode: refresh only entries where track_price=True or for_trade=True.
    """
    from sqlalchemy import select, or_
    from models import CollectionEntry, Card
    from routers.settings import get_pricing_mode

    async with AsyncSessionLocal() as session:
        pricing_mode = await get_pricing_mode(session)

    if pricing_mode != "full":
        # Collection-only: only refresh explicitly tracked cards
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(CollectionEntry.card_api_id).distinct().where(
                    or_(CollectionEntry.track_price == True, CollectionEntry.for_trade == True),
                    CollectionEntry.quantity > 0,
                )
            )
            all_ids = [row[0] for row in result.fetchall()]

        if not all_ids:
            logger.info(
                "Nightly price refresh skipped — no price-tracked cards in collection-only mode"
            )
            return
        logger.info(
            "Collection-only mode: refreshing %d price-tracked card(s)", len(all_ids)
        )
    else:
        logger.info("Nightly price refresh starting")

        # Full mode: refresh every card in the collection
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


async def backfill_incomplete_sets() -> None:
    """Fill in sets where the card cache is incomplete.

    Only considers sets that appear in the user's collection.  Runs at :05
    every hour (5 min after the hourly counter resets) so it has maximum quota.
    Stops immediately if the hourly API limit is reached and will resume next hour.
    """
    from sqlalchemy import select, func
    from models import Set, Card, CollectionEntry
    from datetime import datetime, timezone

    logger.info("Backfill incomplete sets — checking collection sets")

    async with AsyncSessionLocal() as session:
        # Sets that have at least one collection entry
        sets_with_entries_result = await session.execute(
            select(Card.set_id).distinct()
            .join(CollectionEntry, CollectionEntry.card_api_id == Card.api_id)
            .where(Card.set_id.is_not(None))
        )
        set_ids = {row.set_id for row in sets_with_entries_result}

        if not set_ids:
            logger.info("Backfill: no sets in collection — nothing to do")
            return

        sets_result = await session.execute(
            select(Set)
            .where(Set.set_id.in_(set_ids))
            .where(Set.card_count > 0)
        )
        all_sets = sets_result.scalars().all()

        counts_result = await session.execute(
            select(Card.set_id, func.count(Card.api_id).label("cnt"))
            .where(Card.set_id.in_(set_ids))
            .group_by(Card.set_id)
        )
        cached_counts = {row.set_id: row.cnt for row in counts_result}

    incomplete = [s for s in all_sets if cached_counts.get(s.set_id, 0) < s.card_count]

    if not incomplete:
        logger.info("Backfill: all collection sets fully cached — nothing to do")
        return

    logger.info("Backfill: %d set(s) need backfilling", len(incomplete))

    filled = 0
    for s in incomplete:
        if pokewallet.is_hourly_limit_reached():
            logger.warning(
                "Backfill: hourly API limit reached — filled %d/%d set(s) this run, will resume next hour",
                filled,
                len(incomplete),
            )
            return

        cached = cached_counts.get(s.set_id, 0)
        logger.info(
            "Backfill: fetching %s (%s) — %d/%d cards cached",
            s.name, s.set_code, cached, s.card_count,
        )

        raw_cards = await pokewallet.get_set_cards(s.set_code or s.set_id)
        if not raw_cards:
            logger.warning("Backfill: no cards returned for %s — skipping", s.set_code)
            continue

        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            for raw in raw_cards:
                api_id = raw.get("api_id", "")
                if not api_id:
                    continue
                existing = await session.get(Card, api_id)
                if not existing:
                    session.add(Card(
                        api_id=api_id,
                        name=raw.get("name", ""),
                        clean_name=raw.get("clean_name") or raw.get("name", ""),
                        set_id=s.set_id,
                        set_code=s.set_code,
                        card_number=raw.get("card_number") or None,
                        rarity=raw.get("rarity") or None,
                        card_type=raw.get("card_type") or None,
                        hp=raw.get("hp") or None,
                        stage=raw.get("stage") or None,
                        image_url=raw.get("image_url") or None,
                        last_fetched_at=now,
                    ))
            await session.commit()

        filled += 1
        logger.info("Backfill: %s complete (%d cards from API)", s.name, len(raw_cards))

    logger.info("Backfill run complete — filled %d set(s)", filled)


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
    scheduler.add_job(
        backfill_incomplete_sets,
        CronTrigger(minute=5),
        id="backfill_incomplete_sets",
        replace_existing=True,
        name="Backfill incomplete set card caches",
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
