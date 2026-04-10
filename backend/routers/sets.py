import logging
import os
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Set, Card
from schemas import SetOut, CardOut
from services import pokewallet

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sets", tags=["sets"])

SET_CACHE_TTL_DAYS = int(os.environ.get("SET_CACHE_TTL_DAYS", "7"))


def _sets_are_stale(sets: list[Set]) -> bool:
    if not sets:
        return True
    oldest = min(s.last_fetched_at for s in sets)
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - oldest > timedelta(days=SET_CACHE_TTL_DAYS)


@router.get("", response_model=list[SetOut])
async def list_sets(session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Set).order_by(Set.release_date.desc()))
    sets = result.scalars().all()

    if _sets_are_stale(sets):
        logger.info("Sets cache stale — fetching from PokéWallet API")
        raw_sets = await pokewallet.get_sets()
        now = datetime.now(timezone.utc)

        for raw in raw_sets:
            set_id = str(raw.get("groupId") or raw.get("id") or raw.get("set_id", ""))
            if not set_id:
                continue
            existing = await session.get(Set, set_id)
            if existing:
                existing.name = raw.get("name", existing.name)
                existing.set_code = raw.get("abbreviation") or raw.get("setCode") or raw.get("set_code")
                existing.language = raw.get("language")
                existing.release_date = raw.get("publishedOn") or raw.get("releaseDate") or raw.get("release_date")
                existing.card_count = raw.get("totalCards") or raw.get("card_count") or 0
                existing.last_fetched_at = now
            else:
                s = Set(
                    set_id=set_id,
                    set_code=raw.get("abbreviation") or raw.get("setCode") or raw.get("set_code"),
                    name=raw.get("name", ""),
                    language=raw.get("language"),
                    release_date=raw.get("publishedOn") or raw.get("releaseDate") or raw.get("release_date"),
                    card_count=raw.get("totalCards") or raw.get("card_count") or 0,
                    last_fetched_at=now,
                )
                session.add(s)

        await session.commit()
        result = await session.execute(select(Set).order_by(Set.release_date.desc()))
        sets = result.scalars().all()

    return sets


@router.get("/{set_id}/cards", response_model=list[CardOut])
async def get_set_cards(set_id: str, session: AsyncSession = Depends(get_db)):
    """Return all cards in a set (from cache, fetching if needed)."""
    result = await session.execute(
        select(Card).where(Card.set_id == set_id).order_by(Card.card_number)
    )
    cards = result.scalars().all()

    if not cards:
        # Fetch from API using set_code
        set_obj = await session.get(Set, set_id)
        set_code = set_obj.set_code if set_obj else set_id

        raw_cards = await pokewallet.get_set_cards(set_code or set_id)
        now = datetime.now(timezone.utc)

        for raw in raw_cards:
            api_id = str(raw.get("productId") or raw.get("id") or raw.get("api_id", ""))
            if not api_id:
                continue
            existing = await session.get(Card, api_id)
            if not existing:
                card = Card(
                    api_id=api_id,
                    name=raw.get("name", ""),
                    clean_name=raw.get("cleanName") or raw.get("clean_name") or raw.get("name", ""),
                    set_id=set_id,
                    set_code=set_code,
                    card_number=raw.get("number") or raw.get("card_number"),
                    rarity=raw.get("rarity"),
                    card_type=raw.get("cardType") or raw.get("card_type"),
                    hp=raw.get("hp"),
                    stage=raw.get("stage"),
                    last_fetched_at=now,
                )
                session.add(card)

        await session.commit()
        result = await session.execute(
            select(Card).where(Card.set_id == set_id).order_by(Card.card_number)
        )
        cards = result.scalars().all()

    return cards
