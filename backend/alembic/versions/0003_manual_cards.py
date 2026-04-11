"""add source and cardmarket_url to cards

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-11

"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('cards', sa.Column(
        'source', sa.String(), nullable=False,
        server_default='pokewallet',
    ))
    op.add_column('cards', sa.Column('cardmarket_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('cards', 'cardmarket_url')
    op.drop_column('cards', 'source')
