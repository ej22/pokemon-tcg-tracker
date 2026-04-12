"""add app_settings table

Revision ID: c17d2f173cf7
Revises: 0004
Create Date: 2026-04-12 14:47:59.767762

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c17d2f173cf7'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.execute(
        "INSERT INTO app_settings (key, value, updated_at) VALUES ('pricing_mode', 'full', NOW())"
    )


def downgrade() -> None:
    op.drop_table("app_settings")
