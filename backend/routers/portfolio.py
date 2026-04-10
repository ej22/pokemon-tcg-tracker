from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import CollectionEntry, Card, PriceCache, Set
from schemas import PortfolioSummary

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummary)
async def portfolio_summary(session: AsyncSession = Depends(get_db)):
    # Total cards (sum of quantity)
    qty_result = await session.execute(
        select(func.sum(CollectionEntry.quantity))
    )
    total_cards = qty_result.scalar() or 0

    # Unique cards
    unique_result = await session.execute(
        select(func.count(CollectionEntry.card_api_id.distinct()))
    )
    total_unique = unique_result.scalar() or 0

    # All collection entries with card info
    entries_result = await session.execute(
        select(CollectionEntry).order_by(CollectionEntry.card_api_id)
    )
    entries = entries_result.scalars().all()

    total_value_eur = Decimal("0")
    cards_with_prices = 0
    cards_without_prices = 0
    set_values: dict[str, dict] = {}

    for entry in entries:
        # Get best price: prefer the variant that matches, else first cardmarket entry
        prices_result = await session.execute(
            select(PriceCache).where(
                PriceCache.card_api_id == entry.card_api_id,
                PriceCache.source == "cardmarket",
            )
        )
        prices = prices_result.scalars().all()

        best_price: Decimal | None = None
        if prices:
            # Try to match variant; fall back to first entry with a trend/avg price
            matched = next(
                (p for p in prices if entry.variant and p.variant_type == entry.variant),
                None,
            )
            candidate = matched or prices[0]
            best_price = candidate.trend_price or candidate.avg_price or candidate.mid_price

        if best_price is not None:
            cards_with_prices += 1
            total_value_eur += best_price * entry.quantity
        else:
            cards_without_prices += 1

        # Aggregate by set
        card = await session.get(Card, entry.card_api_id)
        set_id = card.set_id if card else None
        set_name = "Unknown Set"
        if set_id:
            set_obj = await session.get(Set, set_id)
            set_name = set_obj.name if set_obj else set_id

        if set_name not in set_values:
            set_values[set_name] = {"set_name": set_name, "total_eur": Decimal("0"), "card_count": 0}
        set_values[set_name]["total_eur"] += best_price * entry.quantity if best_price else Decimal("0")
        set_values[set_name]["card_count"] += entry.quantity

    value_by_set = sorted(
        [
            {
                "set_name": v["set_name"],
                "total_eur": float(v["total_eur"]),
                "card_count": v["card_count"],
            }
            for v in set_values.values()
        ],
        key=lambda x: x["total_eur"],
        reverse=True,
    )

    return PortfolioSummary(
        total_cards=total_cards,
        total_unique_cards=total_unique,
        total_value_eur=total_value_eur if total_value_eur > 0 else None,
        cards_with_prices=cards_with_prices,
        cards_without_prices=cards_without_prices,
        value_by_set=value_by_set,
    )
