"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sets",
        sa.Column("set_id", sa.String(), primary_key=True),
        sa.Column("set_code", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("release_date", sa.String(), nullable=True),
        sa.Column("card_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_fetched_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "cards",
        sa.Column("api_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("clean_name", sa.String(), nullable=False),
        sa.Column("set_id", sa.String(), sa.ForeignKey("sets.set_id"), nullable=True),
        sa.Column("set_code", sa.String(), nullable=True),
        sa.Column("card_number", sa.String(), nullable=True),
        sa.Column("rarity", sa.String(), nullable=True),
        sa.Column("card_type", sa.String(), nullable=True),
        sa.Column("hp", sa.String(), nullable=True),
        sa.Column("stage", sa.String(), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "collection",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("card_api_id", sa.String(), sa.ForeignKey("cards.api_id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("condition", sa.String(), nullable=False, server_default="NM"),
        sa.Column("language", sa.String(), nullable=False, server_default="English"),
        sa.Column("variant", sa.String(), nullable=True),
        sa.Column("purchase_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("purchase_currency", sa.String(), nullable=False, server_default="EUR"),
        sa.Column("date_acquired", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("card_api_id", sa.String(), sa.ForeignKey("cards.api_id"), nullable=False),
        sa.Column("variant_type", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("low_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("mid_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("market_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("avg_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("trend_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="EUR"),
        sa.Column("fetched_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "price_cache",
        sa.Column("card_api_id", sa.String(), sa.ForeignKey("cards.api_id"), primary_key=True),
        sa.Column("variant_type", sa.String(), primary_key=True),
        sa.Column("source", sa.String(), primary_key=True),
        sa.Column("low_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("mid_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("market_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("avg_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("trend_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="EUR"),
        sa.Column("last_fetched_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Indexes for common queries
    op.create_index("ix_collection_card_api_id", "collection", ["card_api_id"])
    op.create_index("ix_price_history_card_api_id", "price_history", ["card_api_id"])
    op.create_index("ix_price_history_fetched_at", "price_history", ["fetched_at"])
    op.create_index("ix_cards_set_id", "cards", ["set_id"])


def downgrade() -> None:
    op.drop_table("price_cache")
    op.drop_table("price_history")
    op.drop_table("collection")
    op.drop_table("cards")
    op.drop_table("sets")
