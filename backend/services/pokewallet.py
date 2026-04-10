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
    """Search for cards by name. Returns raw API results."""
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
        # API may return a list or {"results": [...]}
        if isinstance(data, list):
            return data
        return data.get("results", data.get("cards", []))


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
        return resp.json()


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
    """Fetch all cards in a set."""
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
        # Handle disambiguation response
        if isinstance(data, dict) and "sets" in data:
            logger.info("Disambiguation response for set %s — multiple matches", set_code)
            return []
        if isinstance(data, list):
            return data
        return data.get("cards", data.get("results", []))


def extract_cardmarket_prices(card_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract CardMarket EUR price entries from a raw card API response.
    Returns a list of dicts: {variant_type, low, mid, avg, trend, currency}.
    """
    prices = []
    raw_prices = card_data.get("prices", {})

    if not raw_prices:
        return prices

    # PokéWallet price structure varies; handle both flat and nested formats
    # Nested: {"cardmarket": {"Normal": {"low": ..., "trend": ...}, ...}}
    # Flat:   {"cardmarket_low": ..., "cardmarket_trend": ...}

    cm = raw_prices.get("cardmarket", {})
    if isinstance(cm, dict):
        for variant, pricing in cm.items():
            if isinstance(pricing, dict):
                prices.append({
                    "variant_type": variant,
                    "low_price": pricing.get("low"),
                    "mid_price": pricing.get("mid"),
                    "market_price": pricing.get("market"),
                    "avg_price": pricing.get("avg") or pricing.get("average"),
                    "trend_price": pricing.get("trend"),
                    "currency": "EUR",
                    "source": "cardmarket",
                })
        if prices:
            return prices

    # Flat fallback — single variant
    flat_trend = raw_prices.get("cardmarket_trend") or raw_prices.get("cm_trend")
    flat_avg = raw_prices.get("cardmarket_avg") or raw_prices.get("cm_avg")
    flat_low = raw_prices.get("cardmarket_low") or raw_prices.get("cm_low")
    if any([flat_trend, flat_avg, flat_low]):
        prices.append({
            "variant_type": "Normal",
            "low_price": flat_low,
            "mid_price": None,
            "market_price": None,
            "avg_price": flat_avg,
            "trend_price": flat_trend,
            "currency": "EUR",
            "source": "cardmarket",
        })

    return prices
