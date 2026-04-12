"""Endpoint for adding a card by PriceCharting product URL.

Used for promo cards absent from PokéWallet (e.g. Black Star Promos).
POST /api/cards/manual  { "url": "https://www.pricecharting.com/game/..." }
Returns the card metadata shape expected by the search/add modal.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models import Card
from services.pricecharting_scraper import (
    InvalidPriceChartingURLError,
    ScrapeParseError,
)
from services.price_cache import scrape_and_store
from services.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cards", tags=["manual-cards"])


class ManualCardRequest(BaseModel):
    url: str


@router.post("/manual")
async def add_manual_card(
    body: ManualCardRequest,
    session: AsyncSession = Depends(get_db),
    _: Optional[str] = Depends(require_auth),
):
    """Scrape a PriceCharting product page and return card metadata + prices.

    Response shape matches the PokéWallet search result so the existing
    add-to-collection modal works unchanged.
    """
    try:
        card = await scrape_and_store(session, body.url)
    except InvalidPriceChartingURLError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ScrapeParseError as e:
        logger.warning("PriceCharting parse error: %s", e)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.warning("PriceCharting scrape error: %s", e)
        raise HTTPException(status_code=502, detail=f"Scrape error: {e}")

    if card is None:
        raise HTTPException(status_code=500, detail="Card not stored after scrape.")

    # Reload with set relationship eager-loaded
    result = await session.execute(
        select(Card).options(selectinload(Card.set)).where(Card.api_id == card.api_id)
    )
    card = result.scalar_one()

    return {
        "api_id":      card.api_id,
        "name":        card.name,
        "clean_name":  card.clean_name,
        "set_id":      card.set_id,
        "set_name":    card.set.name if card.set else (card.set_code or ""),
        "set_code":    card.set_code or "",
        "card_number": card.card_number or "",
        "rarity":      card.rarity or "",
        "image_url":   card.image_url or "",
        "source":      card.source,
        "source_url":  card.source_url,
    }
