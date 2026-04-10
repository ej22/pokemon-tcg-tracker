from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


# ── Sets ──────────────────────────────────────────────────────────────────────

class SetOut(BaseModel):
    set_id: str
    set_code: Optional[str]
    name: str
    language: Optional[str]
    release_date: Optional[str]
    card_count: int
    last_fetched_at: datetime

    model_config = {"from_attributes": True}


# ── Cards ─────────────────────────────────────────────────────────────────────

class CardOut(BaseModel):
    api_id: str
    name: str
    clean_name: str
    set_id: Optional[str]
    set_code: Optional[str]
    card_number: Optional[str]
    rarity: Optional[str]
    card_type: Optional[str]
    hp: Optional[str]
    stage: Optional[str]
    image_url: Optional[str]
    last_fetched_at: datetime

    model_config = {"from_attributes": True}


# ── Collection ────────────────────────────────────────────────────────────────

class CollectionEntryCreate(BaseModel):
    card_api_id: str
    quantity: int = 1
    condition: str = "NM"
    language: str = "English"
    variant: Optional[str] = None
    purchase_price: Optional[Decimal] = None
    purchase_currency: str = "EUR"
    date_acquired: Optional[date] = None
    notes: Optional[str] = None


class CollectionEntryUpdate(BaseModel):
    quantity: Optional[int] = None
    condition: Optional[str] = None
    language: Optional[str] = None
    variant: Optional[str] = None
    purchase_price: Optional[Decimal] = None
    purchase_currency: Optional[str] = None
    date_acquired: Optional[date] = None
    notes: Optional[str] = None


class PriceCacheOut(BaseModel):
    variant_type: str
    source: str
    low_price: Optional[Decimal]
    mid_price: Optional[Decimal]
    market_price: Optional[Decimal]
    avg_price: Optional[Decimal]
    trend_price: Optional[Decimal]
    currency: str
    last_fetched_at: datetime

    model_config = {"from_attributes": True}


class CollectionEntryOut(BaseModel):
    id: int
    card_api_id: str
    quantity: int
    condition: str
    language: str
    variant: Optional[str]
    purchase_price: Optional[Decimal]
    purchase_currency: str
    date_acquired: Optional[date]
    notes: Optional[str]
    created_at: datetime
    card: CardOut
    prices: list[PriceCacheOut] = []

    model_config = {"from_attributes": True}


# ── Prices ────────────────────────────────────────────────────────────────────

class PriceHistoryOut(BaseModel):
    id: int
    card_api_id: str
    variant_type: str
    source: str
    low_price: Optional[Decimal]
    mid_price: Optional[Decimal]
    market_price: Optional[Decimal]
    avg_price: Optional[Decimal]
    trend_price: Optional[Decimal]
    currency: str
    fetched_at: datetime

    model_config = {"from_attributes": True}


# ── Portfolio ─────────────────────────────────────────────────────────────────

class PortfolioSummary(BaseModel):
    total_cards: int
    total_unique_cards: int
    total_value_eur: Optional[Decimal]
    cards_with_prices: int
    cards_without_prices: int
    value_by_set: list[dict]
