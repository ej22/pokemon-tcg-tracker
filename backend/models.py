from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import (
    String, Integer, Numeric, Text, DateTime, Date,
    ForeignKey, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Set(Base):
    __tablename__ = "sets"

    set_id: Mapped[str] = mapped_column(String, primary_key=True)
    set_code: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    release_date: Mapped[str | None] = mapped_column(String, nullable=True)
    card_count: Mapped[int] = mapped_column(Integer, default=0)
    last_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    cards: Mapped[list["Card"]] = relationship("Card", back_populates="set")


class Card(Base):
    __tablename__ = "cards"

    api_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    clean_name: Mapped[str] = mapped_column(String, nullable=False)
    set_id: Mapped[str | None] = mapped_column(String, ForeignKey("sets.set_id"), nullable=True)
    set_code: Mapped[str | None] = mapped_column(String, nullable=True)
    card_number: Mapped[str | None] = mapped_column(String, nullable=True)
    rarity: Mapped[str | None] = mapped_column(String, nullable=True)
    card_type: Mapped[str | None] = mapped_column(String, nullable=True)
    hp: Mapped[str | None] = mapped_column(String, nullable=True)
    stage: Mapped[str | None] = mapped_column(String, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    set: Mapped["Set | None"] = relationship("Set", back_populates="cards")
    collection_entries: Mapped[list["CollectionEntry"]] = relationship(
        "CollectionEntry", back_populates="card"
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="card"
    )
    price_cache: Mapped[list["PriceCache"]] = relationship(
        "PriceCache", back_populates="card"
    )


class CollectionEntry(Base):
    __tablename__ = "collection"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_api_id: Mapped[str] = mapped_column(String, ForeignKey("cards.api_id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    condition: Mapped[str] = mapped_column(String, default="NM")
    language: Mapped[str] = mapped_column(String, default="English")
    variant: Mapped[str | None] = mapped_column(String, nullable=True)
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    purchase_currency: Mapped[str] = mapped_column(String, default="EUR")
    date_acquired: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    card: Mapped["Card"] = relationship("Card", back_populates="collection_entries")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_api_id: Mapped[str] = mapped_column(String, ForeignKey("cards.api_id"), nullable=False)
    variant_type: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)  # "cardmarket"
    low_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    mid_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    market_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    avg_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    trend_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String, default="EUR")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    card: Mapped["Card"] = relationship("Card", back_populates="price_history")


class PriceCache(Base):
    __tablename__ = "price_cache"

    card_api_id: Mapped[str] = mapped_column(
        String, ForeignKey("cards.api_id"), primary_key=True
    )
    variant_type: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, primary_key=True)
    low_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    mid_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    market_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    avg_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    trend_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String, default="EUR")
    last_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    card: Mapped["Card"] = relationship("Card", back_populates="price_cache")
