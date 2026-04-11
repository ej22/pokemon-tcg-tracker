"""Cache logic and staleness checks for card prices."""
import logging
import os
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models import Card, PriceCache, PriceHistory
from services import pokewallet

logger = logging.getLogger(__name__)

PRICE_CACHE_TTL_HOURS = int(os.environ.get("PRICE_CACHE_TTL_HOURS", "24"))


def _is_stale(last_fetched_at: datetime, ttl_hours: int) -> bool:
    if last_fetched_at.tzinfo is None:
        last_fetched_at = last_fetched_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - last_fetched_at > timedelta(hours=ttl_hours)


async def _upsert_card_metadata(session: AsyncSession, raw_card_data: dict) -> None:
    """
    Insert or update card metadata from a raw PokéWallet API response.
    The API nests card info under 'card_info'.
    """
    api_id = raw_card_data.get("id") or raw_card_data.get("api_id")
    if not api_id:
        return

    info = raw_card_data.get("card_info", {})
    now = datetime.now(timezone.utc)

    name = info.get("name") or raw_card_data.get("name", "")
    clean_name = info.get("clean_name") or name
    set_id = str(info.get("set_id") or raw_card_data.get("set_id") or "") or None
    set_code = info.get("set_code") or raw_card_data.get("set_code") or None
    set_name = info.get("set_name") or raw_card_data.get("set_name") or ""

    if set_id:
        from models import Set as SetModel
        existing_set = await session.get(SetModel, set_id)
        if not existing_set:
            placeholder_set = SetModel(
                set_id=set_id,
                set_code=set_code,
                name=set_name or set_id,
                last_fetched_at=now,
                card_count=0,
            )
            session.add(placeholder_set)
            await session.flush()

    existing = await session.get(Card, str(api_id))
    if existing:
        existing.name = name
        existing.clean_name = clean_name
        existing.set_id = set_id
        existing.set_code = set_code
        existing.card_number = info.get("card_number") or raw_card_data.get("card_number")
        existing.rarity = info.get("rarity") or raw_card_data.get("rarity")
        existing.card_type = info.get("card_type") or raw_card_data.get("card_type")
        existing.hp = info.get("hp") or raw_card_data.get("hp")
        existing.stage = info.get("stage") or raw_card_data.get("stage")
        existing.image_url = info.get("image_url") or raw_card_data.get("image_url") or existing.image_url
        existing.last_fetched_at = now
    else:
        card = Card(
            api_id=str(api_id),
            name=name,
            clean_name=clean_name,
            set_id=set_id,
            set_code=set_code,
            card_number=info.get("card_number") or raw_card_data.get("card_number"),
            rarity=info.get("rarity") or raw_card_data.get("rarity"),
            card_type=info.get("card_type") or raw_card_data.get("card_type"),
            hp=info.get("hp") or raw_card_data.get("hp"),
            stage=info.get("stage") or raw_card_data.get("stage"),
            image_url=info.get("image_url") or raw_card_data.get("image_url") or None,
            last_fetched_at=now,
        )
        session.add(card)


async def _upsert_pc_card(session: AsyncSession, scraped, eur_ungraded, eur_new) -> None:
    """Insert or update a Card row from a PriceCharting ScrapedCard."""
    from models import Set as SetModel

    now = datetime.now(timezone.utc)
    set_id_placeholder = f"pc_{scraped.set_code.lower()}"

    existing_set = await session.get(SetModel, set_id_placeholder)
    if not existing_set:
        session.add(SetModel(
            set_id=set_id_placeholder,
            set_code=scraped.set_code,
            name=scraped.set_name or scraped.set_code,
            last_fetched_at=now,
            card_count=0,
        ))
        await session.flush()

    existing = await session.get(Card, scraped.api_id)
    if existing:
        existing.name = scraped.name
        existing.clean_name = scraped.name
        existing.set_id = set_id_placeholder
        existing.set_code = scraped.set_code
        existing.card_number = scraped.card_number
        existing.image_url = scraped.image_url or existing.image_url
        existing.source_url = scraped.url
        existing.source = "pricecharting_scrape"
        existing.last_fetched_at = now
    else:
        session.add(Card(
            api_id=scraped.api_id,
            name=scraped.name,
            clean_name=scraped.name,
            set_id=set_id_placeholder,
            set_code=scraped.set_code,
            card_number=scraped.card_number,
            image_url=scraped.image_url,
            source_url=scraped.url,
            source="pricecharting_scrape",
            last_fetched_at=now,
        ))


async def _store_prices(
    session: AsyncSession, card_api_id: str, price_entries: list[dict]
) -> None:
    """Persist new price records to price_history and upsert price_cache."""
    if not price_entries:
        return

    now = datetime.now(timezone.utc)

    for entry in price_entries:
        session.add(PriceHistory(
            card_api_id=card_api_id,
            variant_type=entry["variant_type"],
            source=entry["source"],
            low_price=entry.get("low_price"),
            mid_price=entry.get("mid_price"),
            market_price=entry.get("market_price"),
            avg_price=entry.get("avg_price"),
            trend_price=entry.get("trend_price"),
            currency=entry.get("currency", "EUR"),
            fetched_at=now,
        ))

        stmt = pg_insert(PriceCache).values(
            card_api_id=card_api_id,
            variant_type=entry["variant_type"],
            source=entry["source"],
            low_price=entry.get("low_price"),
            mid_price=entry.get("mid_price"),
            market_price=entry.get("market_price"),
            avg_price=entry.get("avg_price"),
            trend_price=entry.get("trend_price"),
            currency=entry.get("currency", "EUR"),
            last_fetched_at=now,
        ).on_conflict_do_update(
            index_elements=["card_api_id", "variant_type", "source"],
            set_={
                "low_price": entry.get("low_price"),
                "mid_price": entry.get("mid_price"),
                "market_price": entry.get("market_price"),
                "avg_price": entry.get("avg_price"),
                "trend_price": entry.get("trend_price"),
                "currency": entry.get("currency", "EUR"),
                "last_fetched_at": now,
            },
        )
        await session.execute(stmt)


def _pc_to_price_entries(eur_ungraded, eur_new) -> list[dict]:
    """Build price_entries from EUR-converted PriceCharting values."""
    if eur_ungraded is None and eur_new is None:
        return []
    return [{
        "variant_type": "normal",
        "source": "pricecharting_scrape",
        "low_price": None,
        "mid_price": None,
        "market_price": eur_ungraded,   # ungraded market value
        "avg_price": eur_ungraded,      # used as the primary display price
        "trend_price": eur_new,         # near-mint/new as high-end reference
        "currency": "EUR",
    }]


async def scrape_and_store(
    session: AsyncSession,
    url: str,
    force_refresh: bool = False,
) -> "Card":
    """Fetch (or return cached) a PriceCharting card with up-to-date EUR prices.

    Returns the Card ORM row. Raises InvalidPriceChartingURLError /
    ScrapeParseError / ScrapeError on failure.
    """
    from services.pricecharting_scraper import canonicalize_url, build_api_id, scrape_card
    from services.currency import get_rate, usd_to_eur

    canonical = canonicalize_url(url)
    api_id = build_api_id(canonical)

    # Return cached data if fresh
    existing_card = await session.get(Card, api_id)
    if existing_card and not force_refresh:
        cached = (await session.execute(
            select(PriceCache).where(PriceCache.card_api_id == api_id)
        )).scalars().all()
        if cached and not any(_is_stale(c.last_fetched_at, PRICE_CACHE_TTL_HOURS) for c in cached):
            logger.debug("Cache hit for PC card %s", api_id)
            return existing_card

    logger.info("Scraping PriceCharting for %s", canonical)
    scraped = await scrape_card(canonical)

    rate = await get_rate()
    eur_ungraded = usd_to_eur(scraped.price_ungraded, rate)
    eur_new = usd_to_eur(scraped.price_new, rate)

    await _upsert_pc_card(session, scraped, eur_ungraded, eur_new)
    await _store_prices(session, scraped.api_id, _pc_to_price_entries(eur_ungraded, eur_new))
    await session.commit()

    return await session.get(Card, api_id)


async def get_price(
    session: AsyncSession,
    card_api_id: str,
    force_refresh: bool = False,
) -> list[PriceCache]:
    """Return latest prices for a card, using the cache when fresh."""
    result = await session.execute(
        select(PriceCache).where(PriceCache.card_api_id == card_api_id)
    )
    cached = result.scalars().all()

    if cached and not force_refresh:
        if not any(_is_stale(c.last_fetched_at, PRICE_CACHE_TTL_HOURS) for c in cached):
            logger.debug("Cache hit for card %s", card_api_id)
            return list(cached)

    card = await session.get(Card, card_api_id)

    # ── PriceCharting scraped card ───────────────────────────────────
    if card and card.source == "pricecharting_scrape" and card.source_url:
        logger.info("Refreshing PC card %s from PriceCharting", card_api_id)
        from services.pricecharting_scraper import scrape_card, ScrapeError
        from services.currency import get_rate, usd_to_eur
        try:
            scraped = await scrape_card(card.source_url)
            rate = await get_rate()
            eur_ungraded = usd_to_eur(scraped.price_ungraded, rate)
            eur_new = usd_to_eur(scraped.price_new, rate)
            await _upsert_pc_card(session, scraped, eur_ungraded, eur_new)
            await _store_prices(session, card_api_id, _pc_to_price_entries(eur_ungraded, eur_new))
            await session.commit()
            result = await session.execute(
                select(PriceCache).where(PriceCache.card_api_id == card_api_id)
            )
            return result.scalars().all()
        except ScrapeError as e:
            logger.warning("PC scrape failed for %s: %s — returning stale cache", card_api_id, e)
            return list(cached)

    # ── PokéWallet card (default) ────────────────────────────────────
    logger.info("Fetching prices from PokéWallet API for card %s", card_api_id)
    card_data = await pokewallet.get_card(card_api_id)
    if not card_data:
        logger.warning("PokéWallet API returned no data for card %s", card_api_id)
        return list(cached)

    await _upsert_card_metadata(session, card_data)
    price_entries = pokewallet.extract_cardmarket_prices(card_data)
    if price_entries:
        await _store_prices(session, card_api_id, price_entries)
        await session.commit()
        result = await session.execute(
            select(PriceCache).where(PriceCache.card_api_id == card_api_id)
        )
        return result.scalars().all()
    else:
        logger.info("No CardMarket prices returned for card %s", card_api_id)
        await session.commit()
        return list(cached)
