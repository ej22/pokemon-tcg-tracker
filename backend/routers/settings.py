from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import AppSetting
from schemas import SettingUpdate
from services.auth import require_auth

router = APIRouter(prefix="/api/settings", tags=["settings"])

_VALID_VALUES = {
    "pricing_mode": {"full", "collection_only"},
    "auto_fetch_full_set": {"enabled", "disabled"},
    "set_images": {"visible", "hidden"},
    "onboarding_complete": {"true", "false"},
    "pokewallet_api_key_status": {"valid", "invalid", "unknown"},
}


async def get_pricing_mode(session: AsyncSession) -> str:
    """Return the current pricing mode. Defaults to 'full' if not set."""
    setting = await session.get(AppSetting, "pricing_mode")
    return setting.value if setting else "full"


async def get_auto_fetch_setting(session: AsyncSession) -> str:
    """Return whether auto-fetching full set card lists is enabled. Defaults to 'disabled'."""
    setting = await session.get(AppSetting, "auto_fetch_full_set")
    return setting.value if setting else "disabled"


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

    setting = await session.get(AppSetting, key)
    if setting:
        setting.value = body.value
        setting.updated_at = datetime.now(timezone.utc)
    else:
        setting = AppSetting(key=key, value=body.value, updated_at=datetime.now(timezone.utc))
        session.add(setting)

    await session.commit()
    return {"key": key, "value": body.value}


async def _upsert_setting(session: AsyncSession, key: str, value: str) -> None:
    setting = await session.get(AppSetting, key)
    if setting:
        setting.value = value
        setting.updated_at = datetime.now(timezone.utc)
    else:
        session.add(AppSetting(key=key, value=value, updated_at=datetime.now(timezone.utc)))
    await session.commit()


@router.post("/validate-api-key")
async def validate_api_key(session: AsyncSession = Depends(get_db)):
    """Test the configured POKEWALLET_API_KEY with a lightweight API call."""
    import os
    api_key = os.environ.get("POKEWALLET_API_KEY", "")
    if not api_key:
        await _upsert_setting(session, "pokewallet_api_key_status", "invalid")
        return {"status": "invalid", "detail": "POKEWALLET_API_KEY is not set in environment"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.pokewallet.io/sets",
                params={"limit": 1},
                headers={"X-API-Key": api_key},
            )
        if resp.status_code in (401, 403):
            await _upsert_setting(session, "pokewallet_api_key_status", "invalid")
            return {"status": "invalid", "detail": "API key rejected (HTTP {})".format(resp.status_code)}
        if not resp.is_success:
            await _upsert_setting(session, "pokewallet_api_key_status", "invalid")
            return {"status": "invalid", "detail": f"Unexpected response: HTTP {resp.status_code}"}
        data = resp.json()
        # PokéWallet sets endpoint returns {"success": true, "data": [...]}
        if not (isinstance(data, dict) and data.get("success")):
            await _upsert_setting(session, "pokewallet_api_key_status", "invalid")
            return {"status": "invalid", "detail": "Unexpected response format from API"}
    except httpx.RequestError as exc:
        await _upsert_setting(session, "pokewallet_api_key_status", "invalid")
        return {"status": "invalid", "detail": f"Network error: {exc}"}

    await _upsert_setting(session, "pokewallet_api_key_status", "valid")
    return {"status": "valid"}


class CompleteOnboardingBody(BaseModel):
    pricing_mode: str
    grouped_layout: str
    auto_fetch_full_set: str = "disabled"
    set_images: str = "visible"


@router.post("/complete-onboarding")
async def complete_onboarding(
    body: CompleteOnboardingBody,
    session: AsyncSession = Depends(get_db),
):
    """Save onboarding preferences and mark onboarding as complete."""
    if body.pricing_mode not in _VALID_VALUES["pricing_mode"]:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid pricing_mode '{body.pricing_mode}'. Allowed: {sorted(_VALID_VALUES['pricing_mode'])}",
        )
    if body.grouped_layout not in {"horizontal", "grid"}:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid grouped_layout '{body.grouped_layout}'. Allowed: ['grid', 'horizontal']",
        )
    if body.auto_fetch_full_set not in _VALID_VALUES["auto_fetch_full_set"]:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid auto_fetch_full_set '{body.auto_fetch_full_set}'. Allowed: {sorted(_VALID_VALUES['auto_fetch_full_set'])}",
        )
    if body.set_images not in _VALID_VALUES["set_images"]:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid set_images '{body.set_images}'. Allowed: {sorted(_VALID_VALUES['set_images'])}",
        )

    await _upsert_setting(session, "pricing_mode", body.pricing_mode)
    await _upsert_setting(session, "auto_fetch_full_set", body.auto_fetch_full_set)
    await _upsert_setting(session, "set_images", body.set_images)
    await _upsert_setting(session, "onboarding_complete", "true")

    return {"success": True, "grouped_layout": body.grouped_layout}
