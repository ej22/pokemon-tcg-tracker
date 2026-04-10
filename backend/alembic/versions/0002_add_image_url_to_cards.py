"""add image_url to cards

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-10

"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('cards', sa.Column('image_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('cards', 'image_url')
