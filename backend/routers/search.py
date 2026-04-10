import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
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
    """Proxy PokéWallet search, caching card metadata."""
    normalised = await pokewallet.search_cards(q)
    now = datetime.now(timezone.utc)
    output = []

    for card in normalised:
        api_id = card["api_id"]
        if not api_id:
            continue

        # Cache card metadata if not already stored
        set_id = str(card["set_id"]) if card.get("set_id") else None
        existing = await session.get(Card, api_id)
        if not existing:
            # Ensure parent set exists (FK constraint)
            if set_id:
                from models import Set as SetModel
                existing_set = await session.get(SetModel, set_id)
                if not existing_set:
                    session.add(SetModel(
                        set_id=set_id,
                        set_code=card.get("set_code") or None,
                        name=card.get("set_name") or set_id,
                        last_fetched_at=now,
                        card_count=0,
                    ))
                    await session.flush()

            session.add(Card(
                api_id=api_id,
                name=card["name"],
                clean_name=card["clean_name"],
                set_id=set_id,
                set_code=card["set_code"] or None,
                card_number=card["card_number"] or None,
                rarity=card["rarity"] or None,
                card_type=card["card_type"] or None,
                hp=card["hp"] or None,
                stage=card["stage"] or None,
                last_fetched_at=now,
            ))

        output.append({
            "api_id":      api_id,
            "name":        card["name"],
            "clean_name":  card["clean_name"],
            "set_id":      card.get("set_id"),
            "set_name":    card.get("set_name", ""),
            "set_code":    card.get("set_code", ""),
            "card_number": card.get("card_number", ""),
            "rarity":      card.get("rarity", ""),
            "image_url":   card.get("image_url", ""),
        })

    await session.commit()
    return output
