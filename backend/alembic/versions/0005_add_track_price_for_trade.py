"""add track_price for_trade columns to collection

Revision ID: 0005features
Revises: c17d2f173cf7
Create Date: 2026-04-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005features'
down_revision: Union[str, None] = 'c17d2f173cf7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'collection',
        sa.Column('track_price', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )
    op.add_column(
        'collection',
        sa.Column('for_trade', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )


def downgrade() -> None:
    op.drop_column('collection', 'for_trade')
    op.drop_column('collection', 'track_price')
