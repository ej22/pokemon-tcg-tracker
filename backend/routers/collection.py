from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models import Card, CollectionEntry, PriceCache, Set
from schemas import CollectionEntryCreate, CollectionEntryOut, CollectionEntryUpdate
from services.price_cache import get_price
from routers.settings import get_pricing_mode

router = APIRouter(prefix="/api/collection", tags=["collection"])


async def _enrich_entry(entry: CollectionEntry, session: AsyncSession) -> dict:
    """Attach latest prices and set metadata to a collection entry for the response."""
    prices_result = await session.execute(
        select(PriceCache).where(PriceCache.card_api_id == entry.card_api_id)
    )
    prices = prices_result.scalars().all()

    # Attach set_name and set_card_count to the card for frontend grouping
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
        "created_at": entry.created_at,
        "card": card_dict,
        "prices": prices,
    }
    return entry_dict


@router.get("", response_model=list[CollectionEntryOut])
async def list_collection(session: AsyncSession = Depends(get_db)):
    result = await session.execute(
        select(CollectionEntry)
        .options(selectinload(CollectionEntry.card))
        .order_by(CollectionEntry.created_at.desc())
    )
    entries = result.scalars().all()

    enriched = []
    for entry in entries:
        enriched.append(await _enrich_entry(entry, session))
    return enriched


@router.post("", response_model=CollectionEntryOut, status_code=201)
async def add_to_collection(
    body: CollectionEntryCreate,
    session: AsyncSession = Depends(get_db),
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
        created_at=datetime.now(timezone.utc),
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)

    # Fetch prices only when pricing mode is enabled
    pricing_mode = await get_pricing_mode(session)
    if pricing_mode == "full":
        await get_price(session, body.card_api_id)

    # Reload with card relationship
    result = await session.execute(
        select(CollectionEntry)
        .options(selectinload(CollectionEntry.card))
        .where(CollectionEntry.id == entry.id)
    )
    entry = result.scalar_one()
    return await _enrich_entry(entry, session)


@router.put("/{entry_id}", response_model=CollectionEntryOut)
async def update_collection_entry(
    entry_id: int,
    body: CollectionEntryUpdate,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(CollectionEntry)
        .options(selectinload(CollectionEntry.card))
        .where(CollectionEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Collection entry not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)

    await session.commit()
    await session.refresh(entry)
    return await _enrich_entry(entry, session)


@router.delete("/{entry_id}", status_code=204)
async def delete_collection_entry(
    entry_id: int,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(CollectionEntry).where(CollectionEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Collection entry not found")

    await session.delete(entry)
    await session.commit()
