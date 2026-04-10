"""All PokéWallet API calls. Never log the API key."""
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.pokewallet.io"

# In-memory rate limit counters
_calls_today: int = 0
_calls_this_hour: int = 0
DAILY_WARN_THRESHOLD = 800
HOURLY_LIMIT = 80


def _get_headers() -> dict[str, str]:
    return {"X-API-Key": os.environ["POKEWALLET_API_KEY"]}


def _track_call() -> None:
    global _calls_today, _calls_this_hour
    _calls_today += 1
    _calls_this_hour += 1
    if _calls_today >= DAILY_WARN_THRESHOLD:
        logger.warning(
            "PokéWallet API: %d calls made today — approaching daily limit of 1000",
            _calls_today,
        )


def reset_hourly_counter() -> None:
    global _calls_this_hour
    _calls_this_hour = 0


def reset_daily_counter() -> None:
    global _calls_today, _calls_this_hour
    _calls_today = 0
    _calls_this_hour = 0


def is_hourly_limit_reached() -> bool:
    return _calls_this_hour >= HOURLY_LIMIT


def get_calls_today() -> int:
    return _calls_today


async def search_cards(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Search for cards. Returns a normalised list of card dicts."""
    if is_hourly_limit_reached():
        logger.warning("Hourly API limit reached, skipping search for: %s", query)
        return []

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{BASE_URL}/search",
            params={"q": query, "limit": limit},
            headers=_get_headers(),
        )
        resp.raise_for_status()
        _track_call()
        data = resp.json()

    raw_results = data.get("results", []) if isinstance(data, dict) else data
    return [_normalise_card(r) for r in raw_results]


async def get_card(card_id: str) -> dict[str, Any] | None:
    """Fetch full card detail including prices."""
    if is_hourly_limit_reached():
        logger.warning("Hourly API limit reached, skipping card fetch: %s", card_id)
        return None

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{BASE_URL}/cards/{card_id}",
            headers=_get_headers(),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        _track_call()
        return resp.json()  # Return raw; callers use extract_* helpers


async def get_sets() -> list[dict[str, Any]]:
    """Fetch all sets from PokéWallet."""
    if is_hourly_limit_reached():
        logger.warning("Hourly API limit reached, skipping sets fetch")
        return []

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{BASE_URL}/sets", headers=_get_headers())
        resp.raise_for_status()
        _track_call()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("results", data.get("sets", []))


async def get_set_cards(set_code: str) -> list[dict[str, Any]]:
    """Fetch all cards in a set (normalised)."""
    if is_hourly_limit_reached():
        logger.warning("Hourly API limit reached, skipping set cards fetch: %s", set_code)
        return []

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{BASE_URL}/sets/{set_code}",
            headers=_get_headers(),
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        _track_call()
        data = resp.json()

    if isinstance(data, dict) and "sets" in data:
        logger.info("Disambiguation response for set %s — multiple matches", set_code)
        return []

    raw_list = data if isinstance(data, list) else data.get("cards", data.get("results", []))
    return [_normalise_card(r) for r in raw_list]


def _normalise_card(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Flatten the nested card_info structure into a top-level dict.
    Handles both search results and set-card lists.
    """
    info = raw.get("card_info", {})
    return {
        "api_id":      raw.get("id") or raw.get("api_id", ""),
        "name":        info.get("name") or raw.get("name", ""),
        "clean_name":  info.get("clean_name") or raw.get("clean_name", ""),
        "set_id":      info.get("set_id") or raw.get("set_id"),
        "set_name":    info.get("set_name") or raw.get("set_name", ""),
        "set_code":    info.get("set_code") or raw.get("set_code", ""),
        "card_number": info.get("card_number") or raw.get("card_number", ""),
        "rarity":      info.get("rarity") or raw.get("rarity", ""),
        "card_type":   info.get("card_type") or raw.get("card_type", ""),
        "hp":          info.get("hp") or raw.get("hp", ""),
        "stage":       info.get("stage") or raw.get("stage", ""),
        "image_url":   info.get("image_url") or raw.get("image_url", ""),
        # Keep originals for price extraction
        "_raw": raw,
    }


def extract_cardmarket_prices(card_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract CardMarket EUR price entries from a raw /cards/{id} API response.
    Returns a list of price dicts ready to store.
    """
    cm = card_data.get("cardmarket", {})
    if not cm:
        return []

    price_list = cm.get("prices", [])
    if not isinstance(price_list, list):
        return []

    results = []
    for p in price_list:
        variant = p.get("variant_type") or "Normal"
        results.append({
            "variant_type":  variant,
            "source":        "cardmarket",
            "low_price":     p.get("low"),
            "mid_price":     None,
            "market_price":  None,
            "avg_price":     p.get("avg"),
            "trend_price":   p.get("trend"),
            "currency":      "EUR",
        })
    return results
