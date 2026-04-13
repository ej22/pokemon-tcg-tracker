"""Proxy card images, with a local disk cache to avoid repeat API calls.

Cache layout (bind-mounted at IMAGE_CACHE_DIR, default /app/image_cache):
  {card_api_id}     — raw image bytes
  {card_api_id}.ct  — content-type string (e.g. "image/jpeg")

Backup the cache with:
  tar -czf image_cache_backup.tar.gz image_cache/
"""
import logging
import os
import pathlib

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

CACHE_DIR = pathlib.Path(os.environ.get("IMAGE_CACHE_DIR", "/app/image_cache"))


def _cache_path(card_api_id: str) -> pathlib.Path:
    return CACHE_DIR / card_api_id


def _ct_path(card_api_id: str) -> pathlib.Path:
    return CACHE_DIR / f"{card_api_id}.ct"


def _read_cache(card_api_id: str) -> tuple[bytes, str] | None:
    """Return (bytes, content_type) from disk cache, or None on miss."""
    p = _cache_path(card_api_id)
    if not p.exists():
        return None
    ct_p = _ct_path(card_api_id)
    content_type = ct_p.read_text().strip() if ct_p.exists() else "image/jpeg"
    return p.read_bytes(), content_type


def _write_cache(card_api_id: str, content: bytes, content_type: str) -> None:
    """Write image bytes and content-type to disk cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(card_api_id).write_bytes(content)
    _ct_path(card_api_id).write_text(content_type)


@router.get("/{card_api_id}")
async def get_card_image(card_api_id: str, session: AsyncSession = Depends(get_db)):
    """Return a card image. Served from disk cache when available; fetched and
    cached on first request. Cached responses use a 7-day browser cache header."""

    # ── Disk cache hit ───────────────────────────────────────────────
    cached = _read_cache(card_api_id)
    if cached:
        content, content_type = cached
        return Response(
            content=content,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=604800"},  # 7 days
        )

    # ── Cache miss: fetch from upstream ─────────────────────────────
    card = await session.get(Card, card_api_id)

    # PriceCharting-scraped card — fetch from Google Storage CDN
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
                logger.warning("PriceCharting image fetch failed for %s: %s", card_api_id, e)
                raise HTTPException(status_code=502, detail="Image fetch failed")

        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Image not found")
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Upstream returned {resp.status_code}")

        content_type = resp.headers.get("content-type", "image/jpeg")
        _write_cache(card_api_id, resp.content, content_type)
        return Response(
            content=resp.content,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=604800"},
        )

    # PokéWallet card (default) — fetch via API key
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
            logger.warning("PokéWallet image fetch failed for %s: %s", card_api_id, e)
            raise HTTPException(status_code=502, detail="Image fetch failed")

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Image not found")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Upstream returned {resp.status_code}")

    content_type = resp.headers.get("content-type", "image/jpeg")
    _write_cache(card_api_id, resp.content, content_type)
    return Response(
        content=resp.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=604800"},
    )
