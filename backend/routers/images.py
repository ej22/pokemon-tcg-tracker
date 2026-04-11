"""Proxy card images.

For PokéWallet cards: proxies PokéWallet's image endpoint (requires API key,
so cannot be called directly from the browser).

For CardMarket-scraped cards: fetches the image URL stored in card.image_url
directly from CardMarket/S3 — no API key required.
"""
import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Card

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/images", tags=["images"])

BASE_URL = "https://api.pokewallet.io"

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@router.get("/{card_api_id}")
async def get_card_image(card_api_id: str, session: AsyncSession = Depends(get_db)):
    """Proxy a card image. Response is cached by the browser for 24 h."""

    card = await session.get(Card, card_api_id)

    # ── PriceCharting-scraped card ───────────────────────────────────
    if card and card.source == "pricecharting_scrape":
        if not card.image_url:
            raise HTTPException(status_code=404, detail="No image URL stored for this card")

        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": _BROWSER_UA},
        ) as client:
            try:
                resp = await client.get(card.image_url)
            except httpx.RequestError as e:
                logger.warning("CardMarket image fetch failed for %s: %s", card_api_id, e)
                raise HTTPException(status_code=502, detail="Image fetch failed")

        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Image not found")
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Upstream returned {resp.status_code}")

        content_type = resp.headers.get("content-type", "image/jpeg")
        return Response(
            content=resp.content,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )

    # ── PokéWallet card (default) ────────────────────────────────────
    api_key = os.environ.get("POKEWALLET_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="API key not configured")

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                f"{BASE_URL}/images/{card_api_id}",
                headers={"X-API-Key": api_key},
            )
        except httpx.RequestError as e:
            logger.warning("Image fetch failed for %s: %s", card_api_id, e)
            raise HTTPException(status_code=502, detail="Image fetch failed")

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Image not found")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Upstream returned {resp.status_code}")

    content_type = resp.headers.get("content-type", "image/jpeg")
    return Response(
        content=resp.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
