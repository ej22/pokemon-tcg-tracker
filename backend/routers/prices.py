from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import CollectionEntry, PriceCache, PriceHistory
from schemas import PriceCacheOut, PriceHistoryOut
from services.price_cache import get_price
from routers.settings import get_pricing_mode

router = APIRouter(prefix="/api/prices", tags=["prices"])


@router.get("/{card_api_id}", response_model=list[PriceCacheOut])
async def get_card_prices(
    card_api_id: str,
    session: AsyncSession = Depends(get_db),
):
    prices = await get_price(session, card_api_id)
    if not prices:
        raise HTTPException(status_code=404, detail="No prices found for this card")
    return prices


@router.get("/{card_api_id}/history", response_model=list[PriceHistoryOut])
async def get_price_history(
    card_api_id: str,
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(PriceHistory)
        .where(PriceHistory.card_api_id == card_api_id)
        .order_by(PriceHistory.fetched_at.asc())
    )
    return result.scalars().all()


@router.post("/refresh", status_code=200)
async def manual_refresh(session: AsyncSession = Depends(get_db)):
    """Force-refresh prices for all cards in the collection."""
    pricing_mode = await get_pricing_mode(session)
    if pricing_mode != "full":
        return {"message": "Pricing is disabled in collection-only mode", "refreshed": 0, "skipped": 0, "total": 0}

    result = await session.execute(
        select(CollectionEntry.card_api_id).distinct()
    )
    card_ids = [row[0] for row in result.fetchall()]

    refreshed = 0
    skipped = 0
    for card_id in card_ids:
        prices = await get_price(session, card_id, force_refresh=True)
        if prices:
            refreshed += 1
        else:
            skipped += 1

    return {
        "message": "Price refresh complete",
        "refreshed": refreshed,
        "skipped": skipped,
        "total": len(card_ids),
    }
