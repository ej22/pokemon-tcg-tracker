from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import AppSetting
from schemas import SettingUpdate
from services.auth import require_auth

router = APIRouter(prefix="/api/settings", tags=["settings"])

_VALID_VALUES = {
    "pricing_mode": {"full", "collection_only"},
}


async def get_pricing_mode(session: AsyncSession) -> str:
    """Return the current pricing mode. Defaults to 'full' if not set."""
    setting = await session.get(AppSetting, "pricing_mode")
    return setting.value if setting else "full"


@router.get("")
async def list_settings(session: AsyncSession = Depends(get_db)):
    """Return all settings as a flat key→value dict."""
    from sqlalchemy import select
    result = await session.execute(select(AppSetting))
    rows = result.scalars().all()
    return {row.key: row.value for row in rows}


@router.put("/{key}")
async def update_setting(
    key: str,
    body: SettingUpdate,
    session: AsyncSession = Depends(get_db),
    _: Optional[str] = Depends(require_auth),
):
    """Update a setting by key. Validates known keys."""
    if key in _VALID_VALUES and body.value not in _VALID_VALUES[key]:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid value '{body.value}' for '{key}'. Allowed: {sorted(_VALID_VALUES[key])}",
        )

    from datetime import datetime, timezone
    setting = await session.get(AppSetting, key)
    if setting:
        setting.value = body.value
        setting.updated_at = datetime.now(timezone.utc)
    else:
        setting = AppSetting(key=key, value=body.value, updated_at=datetime.now(timezone.utc))
        session.add(setting)

    await session.commit()
    return {"key": key, "value": body.value}
