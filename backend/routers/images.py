"""Proxy card images from PokéWallet (requires API key, so can't be called directly from browser)."""
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/images", tags=["images"])

BASE_URL = "https://api.pokewallet.io"


@router.get("/{card_api_id}")
async def get_card_image(card_api_id: str):
    """Proxy a card image from PokéWallet. Response is cached by the browser for 24 h."""
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
