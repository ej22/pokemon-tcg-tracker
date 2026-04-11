"""USD → EUR conversion using the Frankfurter API (ECB data, no key required).

The rate is cached in memory for 24 hours. Call refresh_rate() once during
the nightly job so that scraped prices always use a fresh rate.

API: https://api.frankfurter.app/latest?from=USD&to=EUR
Response: {"amount":1.0,"base":"USD","date":"2026-04-11","rates":{"EUR":0.9234}}
"""
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP

import httpx

logger = logging.getLogger(__name__)

_FRANKFURTER_URL = "https://api.frankfurter.app/latest?from=USD&to=EUR"
_CACHE_TTL_HOURS = 24

# Module-level cache
_usd_eur_rate: Decimal | None = None
_rate_fetched_at: datetime | None = None

# Fallback rate used when the API is unreachable
_FALLBACK_RATE = Decimal("0.92")


def _is_stale() -> bool:
    if _rate_fetched_at is None:
        return True
    age = datetime.now(timezone.utc) - _rate_fetched_at
    return age > timedelta(hours=_CACHE_TTL_HOURS)


async def refresh_rate() -> Decimal:
    """Fetch a fresh USD→EUR rate and update the in-memory cache.
    Returns the new rate (or the fallback on failure).
    """
    global _usd_eur_rate, _rate_fetched_at
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_FRANKFURTER_URL)
        resp.raise_for_status()
        data = resp.json()
        rate = Decimal(str(data["rates"]["EUR"]))
        _usd_eur_rate = rate
        _rate_fetched_at = datetime.now(timezone.utc)
        logger.info("USD/EUR rate refreshed: 1 USD = %s EUR (date: %s)", rate, data.get("date"))
        return rate
    except Exception as e:
        logger.warning("Failed to fetch USD/EUR rate from Frankfurter: %s — using fallback %s", e, _FALLBACK_RATE)
        if _usd_eur_rate is None:
            _usd_eur_rate = _FALLBACK_RATE
        return _usd_eur_rate


async def get_rate() -> Decimal:
    """Return the cached USD→EUR rate, refreshing if stale."""
    if _is_stale():
        return await refresh_rate()
    return _usd_eur_rate  # type: ignore[return-value]


def usd_to_eur(usd: Decimal | None, rate: Decimal) -> Decimal | None:
    """Convert a USD Decimal to EUR, rounded to 2 dp. Returns None for None input."""
    if usd is None:
        return None
    return (usd * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
