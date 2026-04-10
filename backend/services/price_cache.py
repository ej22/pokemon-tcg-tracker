"""Cache logic and staleness checks for card prices."""
import logging
import os
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, delete
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


async def _upsert_card_metadata(session: AsyncSession, card_data: dict) -> None:
    """Insert or update card metadata from a raw API response."""
    api_id = card_data.get("id") or card_data.get("api_id") or card_data.get("productId")
    if not api_id:
        return

    existing = await session.get(Card, str(api_id))
    now = datetime.now(timezone.utc)

    name = card_data.get("name", "")
    clean_name = card_data.get("cleanName") or card_data.get("clean_name") or name
    set_id = str(card_data.get("groupId") or card_data.get("set_id") or "")
    set_code = card_data.get("setCode") or card_data.get("set_code") or ""

    if existing:
        existing.name = name
        existing.clean_name = clean_name
        existing.set_id = set_id or None
        existing.set_code = set_code or None
        existing.card_number = card_data.get("number") or card_data.get("card_number")
        existing.rarity = card_data.get("rarity")
        existing.card_type = card_data.get("cardType") or card_data.get("card_type")
        existing.hp = card_data.get("hp")
        existing.stage = card_data.get("stage")
        existing.last_fetched_at = now
    else:
        card = Card(
            api_id=str(api_id),
            name=name,
            clean_name=clean_name,
            set_id=set_id or None,
            set_code=set_code or None,
            card_number=card_data.get("number") or card_data.get("card_number"),
            rarity=card_data.get("rarity"),
            card_type=card_data.get("cardType") or card_data.get("card_type"),
            hp=card_data.get("hp"),
            stage=card_data.get("stage"),
            last_fetched_at=now,
        )
        session.add(card)


async def _store_prices(
    session: AsyncSession, card_api_id: str, price_entries: list[dict]
) -> None:
    """Persist new price records to price_history and upsert price_cache."""
    if not price_entries:
        return

    now = datetime.now(timezone.utc)

    for entry in price_entries:
        # Append to history
        history = PriceHistory(
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
        )
        session.add(history)

        # Upsert price_cache (PostgreSQL ON CONFLICT DO UPDATE)
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


async def get_price(
    session: AsyncSession,
    card_api_id: str,
    force_refresh: bool = False,
) -> list[PriceCache]:
    """
    Return latest prices for a card.
    Checks the cache first; only calls the API if data is missing or stale.
    """
    result = await session.execute(
        select(PriceCache).where(PriceCache.card_api_id == card_api_id)
    )
    cached = result.scalars().all()

    if cached and not force_refresh:
        # Check if any entry is stale
        if not any(_is_stale(c.last_fetched_at, PRICE_CACHE_TTL_HOURS) for c in cached):
            logger.debug("Cache hit for card %s", card_api_id)
            return list(cached)

    # Cache miss or stale — fetch from API
    logger.info("Fetching prices from API for card %s", card_api_id)
    card_data = await pokewallet.get_card(card_api_id)
    if not card_data:
        logger.warning("API returned no data for card %s", card_api_id)
        return list(cached)  # Return stale data rather than nothing

    await _upsert_card_metadata(session, card_data)

    price_entries = pokewallet.extract_cardmarket_prices(card_data)
    if price_entries:
        await _store_prices(session, card_api_id, price_entries)
        await session.commit()
        # Re-fetch from DB
        result = await session.execute(
            select(PriceCache).where(PriceCache.card_api_id == card_api_id)
        )
        return result.scalars().all()
    else:
        logger.info("No CardMarket prices returned for card %s", card_api_id)
        await session.commit()
        return list(cached)
