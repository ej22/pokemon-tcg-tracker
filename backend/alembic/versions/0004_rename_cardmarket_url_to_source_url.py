"""rename cardmarket_url to source_url on cards

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-11

"""
from alembic import op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('cards', 'cardmarket_url', new_column_name='source_url')


def downgrade() -> None:
    op.alter_column('cards', 'source_url', new_column_name='cardmarket_url')
