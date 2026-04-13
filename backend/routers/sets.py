import logging
import os
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Set, Card, CollectionEntry
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


@router.get("/mine")
async def list_owned_sets(session: AsyncSession = Depends(get_db)):
    """Return only sets the user has collection entries in, with owned card count."""
    count_result = await session.execute(
        select(Card.set_id, func.sum(CollectionEntry.quantity).label("owned_count"))
        .join(CollectionEntry, CollectionEntry.card_api_id == Card.api_id)
        .where(Card.set_id.is_not(None))
        .group_by(Card.set_id)
    )
    set_counts = {row.set_id: int(row.owned_count) for row in count_result}

    if not set_counts:
        return []

    sets_result = await session.execute(
        select(Set)
        .where(Set.set_id.in_(set_counts.keys()))
        .order_by(Set.release_date.desc())
    )
    sets = sets_result.scalars().all()

    return [
        {
            "set_id": s.set_id,
            "set_code": s.set_code,
            "name": s.name,
            "language": s.language,
            "release_date": s.release_date,
            "card_count": s.card_count,
            "owned_count": set_counts.get(s.set_id, 0),
        }
        for s in sets
    ]


@router.get("", response_model=list[SetOut])
async def list_sets(session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Set).order_by(Set.release_date.desc()))
    sets = result.scalars().all()

    if _sets_are_stale(sets):
        logger.info("Sets cache stale — fetching from PokéWallet API")
        raw_sets = await pokewallet.get_sets()
        now = datetime.now(timezone.utc)

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
        result = await session.execute(select(Set).order_by(Set.release_date.desc()))
        sets = result.scalars().all()

    return sets


@router.get("/{set_id}/cards")
async def get_set_cards(set_id: str, session: AsyncSession = Depends(get_db)):
    """Return all cards in a set (from cache, fetching if needed), with owned_quantity per card."""
    result = await session.execute(
        select(Card).where(Card.set_id == set_id).order_by(Card.card_number)
    )
    cards = result.scalars().all()

    # Always resolve the set object so we can compare cached count vs expected count
    set_obj = await session.get(Set, set_id)
    set_code = set_obj.set_code if set_obj else set_id
    expected_count = (set_obj.card_count or 0) if set_obj else 0

    if not cards or (expected_count > 0 and len(cards) < expected_count):
        # Cache is empty or incomplete — fetch the full set from the API
        raw_cards = await pokewallet.get_set_cards(set_code or set_id)
        now = datetime.now(timezone.utc)

        for raw in raw_cards:
            # raw_cards are already normalised by pokewallet.get_set_cards
            api_id = raw.get("api_id", "")
            if not api_id:
                continue
            existing = await session.get(Card, api_id)
            if not existing:
                card = Card(
                    api_id=api_id,
                    name=raw.get("name", ""),
                    clean_name=raw.get("clean_name") or raw.get("name", ""),
                    set_id=set_id,
                    set_code=set_code,
                    card_number=raw.get("card_number") or None,
                    rarity=raw.get("rarity") or None,
                    card_type=raw.get("card_type") or None,
                    hp=raw.get("hp") or None,
                    stage=raw.get("stage") or None,
                    image_url=raw.get("image_url") or None,
                    last_fetched_at=now,
                )
                session.add(card)

        await session.commit()
        result = await session.execute(
            select(Card).where(Card.set_id == set_id).order_by(Card.card_number)
        )
        cards = result.scalars().all()

    # Fetch ownership quantities for cards in this set (quantity > 0 only; placeholders don't count)
    card_api_ids = [c.api_id for c in cards]
    ownership_result = await session.execute(
        select(
            CollectionEntry.card_api_id,
            func.sum(CollectionEntry.quantity).label("total_qty"),
        )
        .where(CollectionEntry.card_api_id.in_(card_api_ids))
        .where(CollectionEntry.quantity > 0)
        .group_by(CollectionEntry.card_api_id)
    )
    owned_map = {row.card_api_id: int(row.total_qty) for row in ownership_result}

    return [
        {**CardOut.model_validate(c).model_dump(), "owned_quantity": owned_map.get(c.api_id, 0)}
        for c in cards
    ]


@router.get("/{set_code}/image")
async def get_set_image(set_code: str):
    """Proxy set artwork from PokéWallet. Cached by the browser for 7 days."""
    api_key = os.environ.get("POKEWALLET_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="API key not configured")

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                f"https://api.pokewallet.io/sets/{set_code}/image",
                headers={"X-API-Key": api_key},
            )
        except httpx.RequestError as exc:
            logger.warning("Set image fetch failed for %s: %s", set_code, exc)
            raise HTTPException(status_code=502, detail="Image fetch failed")

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Set image not found")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Upstream returned {resp.status_code}")

    content_type = resp.headers.get("content-type", "image/png")
    return Response(
        content=resp.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=604800"},  # 7 days
    )
