"""add onboarding settings

Revision ID: 0006onboarding
Revises: 0005features
Create Date: 2026-04-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '0006onboarding'
down_revision: Union[str, None] = '0005features'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Always seed api key status as unknown
    op.execute(
        "INSERT INTO app_settings (key, value, updated_at) "
        "VALUES ('pokewallet_api_key_status', 'unknown', NOW()) "
        "ON CONFLICT (key) DO NOTHING"
    )
    # For existing deployments (collection already has data), skip onboarding.
    # For fresh installs, show the wizard.
    op.execute(
        """
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (
            'onboarding_complete',
            CASE WHEN (SELECT COUNT(*) FROM collection) > 0 THEN 'true' ELSE 'false' END,
            NOW()
        )
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM app_settings WHERE key IN ('onboarding_complete', 'pokewallet_api_key_status')"
    )
