from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models import Card, CollectionEntry, PriceCache, Set
from schemas import CollectionEntryCreate, CollectionEntryOut, CollectionEntryUpdate
from services.price_cache import get_price
from services.auth import require_auth
from routers.settings import get_pricing_mode

router = APIRouter(prefix="/api/collection", tags=["collection"])


class BulkMissingRequest(BaseModel):
    set_id: str


async def _enrich_entry(entry: CollectionEntry, session: AsyncSession) -> dict:
    """Attach latest prices and set metadata to a collection entry for the response."""
    prices_result = await session.execute(
        select(PriceCache).where(PriceCache.card_api_id == entry.card_api_id)
    )
    prices = prices_result.scalars().all()

    card = entry.card
    set_name = None
    set_card_count = None
    if card.set_id:
        card_set = await session.get(Set, card.set_id)
        if card_set:
            set_name = card_set.name
            set_card_count = card_set.card_count

    card_dict = {
        "api_id": card.api_id,
        "name": card.name,
        "clean_name": card.clean_name,
        "set_id": card.set_id,
        "set_code": card.set_code,
        "set_name": set_name,
        "set_card_count": set_card_count,
        "card_number": card.card_number,
        "rarity": card.rarity,
        "card_type": card.card_type,
        "hp": card.hp,
        "stage": card.stage,
        "image_url": card.image_url,
        "source": card.source,
        "source_url": card.source_url,
        "last_fetched_at": card.last_fetched_at,
    }

    entry_dict = {
        "id": entry.id,
        "card_api_id": entry.card_api_id,
        "quantity": entry.quantity,
        "condition": entry.condition,
        "language": entry.language,
        "variant": entry.variant,
        "purchase_price": entry.purchase_price,
        "purchase_currency": entry.purchase_currency,
        "date_acquired": entry.date_acquired,
        "notes": entry.notes,
        "track_price": entry.track_price,
        "for_trade": entry.for_trade,
        "created_at": entry.created_at,
        "card": card_dict,
        "prices": prices,
    }
    return entry_dict


@router.get("", response_model=list[CollectionEntryOut])
async def list_collection(
    for_trade: Optional[bool] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """List collection entries. Pass ?for_trade=true to filter to trade binder entries."""
    stmt = (
        select(CollectionEntry)
        .options(selectinload(CollectionEntry.card))
        .order_by(CollectionEntry.created_at.desc())
    )
    if for_trade is not None:
        stmt = stmt.where(CollectionEntry.for_trade == for_trade)

    result = await session.execute(stmt)
    entries = result.scalars().all()

    enriched = []
    for entry in entries:
        enriched.append(await _enrich_entry(entry, session))
    return enriched


@router.post("", response_model=CollectionEntryOut, status_code=201)
async def add_to_collection(
    body: CollectionEntryCreate,
    session: AsyncSession = Depends(get_db),
    _: Optional[str] = Depends(require_auth),
):
    # Ensure card exists in our DB (fetch from API if not already cached)
    card = await session.get(Card, body.card_api_id)
    if not card:
        from services import pokewallet
        from services.price_cache import _upsert_card_metadata

        raw_data = await pokewallet.get_card(body.card_api_id)
        if not raw_data:
            raise HTTPException(status_code=404, detail="Card not found in PokéWallet API")
        await _upsert_card_metadata(session, raw_data)
        await session.commit()

    entry = CollectionEntry(
        card_api_id=body.card_api_id,
        quantity=body.quantity,
        condition=body.condition,
        language=body.language,
        variant=body.variant,
        purchase_price=body.purchase_price,
        purchase_currency=body.purchase_currency,
        date_acquired=body.date_acquired,
        notes=body.notes,
        track_price=body.track_price,
        for_trade=body.for_trade,
        created_at=datetime.now(timezone.utc),
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)

    # Determine whether to fetch prices:
    # - quantity=0 (missing card placeholder): never fetch
    # - full mode: always fetch
    # - collection_only: fetch only if track_price OR for_trade is set
    # - for_trade always triggers a fetch regardless of mode
    pricing_mode = await get_pricing_mode(session)
    should_fetch = False
    if body.quantity > 0:
        if pricing_mode == "full":
            should_fetch = True
        elif body.for_trade:
            should_fetch = True
        elif pricing_mode == "collection_only" and body.track_price:
            should_fetch = True

    if should_fetch:
        await get_price(session, body.card_api_id)

    # Reload with card relationship
    result = await session.execute(
        select(CollectionEntry)
        .options(selectinload(CollectionEntry.card))
        .where(CollectionEntry.id == entry.id)
    )
    entry = result.scalar_one()
    return await _enrich_entry(entry, session)


@router.post("/bulk-missing")
async def bulk_missing(
    body: BulkMissingRequest,
    session: AsyncSession = Depends(get_db),
    _: Optional[str] = Depends(require_auth),
):
    """Add zero-quantity placeholder entries for every card in a set not yet in the collection.

    Requires that the set's cards have been cached (i.e. the set detail page has been
    visited at least once).  Returns ``{"added": <count>}``.
    """
    # Cards in this set that are already cached
    cards_result = await session.execute(
        select(Card).where(Card.set_id == body.set_id)
    )
    set_cards = cards_result.scalars().all()

    if not set_cards:
        return {"added": 0}

    card_ids = [c.api_id for c in set_cards]

    # Existing collection entries for any of those cards
    existing_result = await session.execute(
        select(CollectionEntry.card_api_id).where(
            CollectionEntry.card_api_id.in_(card_ids)
        )
    )
    existing_ids = {row[0] for row in existing_result.fetchall()}

    missing_cards = [c for c in set_cards if c.api_id not in existing_ids]
    now = datetime.now(timezone.utc)
    for card in missing_cards:
        session.add(CollectionEntry(
            card_api_id=card.api_id,
            quantity=0,
            condition="NM",
            language="English",
            created_at=now,
        ))

    await session.commit()
    return {"added": len(missing_cards)}


@router.put("/{entry_id}", response_model=CollectionEntryOut)
async def update_collection_entry(
    entry_id: int,
    body: CollectionEntryUpdate,
    session: AsyncSession = Depends(get_db),
    _: Optional[str] = Depends(require_auth),
):
    result = await session.execute(
        select(CollectionEntry)
        .options(selectinload(CollectionEntry.card))
        .where(CollectionEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Collection entry not found")

    # Capture previous flag values before applying the update
    prev_track_price = entry.track_price
    prev_for_trade = entry.for_trade

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)

    await session.commit()
    await session.refresh(entry)

    # Trigger a price fetch when relevant flags are toggled on
    pricing_mode = await get_pricing_mode(session)
    should_fetch = False
    if entry.quantity > 0:
        # track_price toggled ON in collection_only mode
        if entry.track_price and not prev_track_price and pricing_mode == "collection_only":
            should_fetch = True
        # for_trade toggled ON — always fetch regardless of mode
        if entry.for_trade and not prev_for_trade:
            should_fetch = True

    if should_fetch:
        await get_price(session, entry.card_api_id)

    return await _enrich_entry(entry, session)


@router.delete("/{entry_id}", status_code=204)
async def delete_collection_entry(
    entry_id: int,
    session: AsyncSession = Depends(get_db),
    _: Optional[str] = Depends(require_auth),
):
    result = await session.execute(
        select(CollectionEntry).where(CollectionEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Collection entry not found")

    await session.delete(entry)
    await session.commit()
