import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Card
from services import pokewallet

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def search(
    q: str = Query(..., min_length=2),
    session: AsyncSession = Depends(get_db),
):
    """Proxy PokéWallet search, caching card metadata results."""
    raw_results = await pokewallet.search_cards(q)
    now = datetime.now(timezone.utc)
    output = []

    for raw in raw_results:
        api_id = str(raw.get("productId") or raw.get("id") or raw.get("api_id", ""))
        if not api_id:
            continue

        # Cache card metadata
        existing = await session.get(Card, api_id)
        if not existing:
            card = Card(
                api_id=api_id,
                name=raw.get("name", ""),
                clean_name=raw.get("cleanName") or raw.get("clean_name") or raw.get("name", ""),
                set_id=str(raw.get("groupId") or raw.get("set_id") or "") or None,
                set_code=raw.get("setCode") or raw.get("set_code"),
                card_number=raw.get("number") or raw.get("card_number"),
                rarity=raw.get("rarity"),
                card_type=raw.get("cardType") or raw.get("card_type"),
                hp=raw.get("hp"),
                stage=raw.get("stage"),
                last_fetched_at=now,
            )
            session.add(card)

        output.append({
            "api_id": api_id,
            "name": raw.get("name", ""),
            "clean_name": raw.get("cleanName") or raw.get("clean_name") or raw.get("name", ""),
            "set_id": str(raw.get("groupId") or raw.get("set_id") or "") or None,
            "set_name": raw.get("setName") or raw.get("set_name") or "",
            "set_code": raw.get("setCode") or raw.get("set_code") or "",
            "card_number": raw.get("number") or raw.get("card_number") or "",
            "rarity": raw.get("rarity") or "",
            "image_url": raw.get("imageUrl") or raw.get("image_url") or "",
        })

    await session.commit()
    return output
