"""Scrape a PriceCharting product page for card metadata and USD prices.

Used for promo cards absent from PokéWallet. The user supplies a
PriceCharting product URL; this module fetches and parses the HTML.

Supported URL form:
  https://www.pricecharting.com/game/{set-slug}/{card-slug}

PriceCharting serves real HTML without Cloudflare challenges, so
curl_cffi with Chrome impersonation is used for a consistent UA but a
plain httpx request would also work.

Prices are returned in USD. The caller is responsible for converting to
EUR before storage (see services/currency.py).
"""
import hashlib
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse, urlunparse, unquote

from selectolax.parser import HTMLParser

logger = logging.getLogger(__name__)

_VALID_HOST = "www.pricecharting.com"
_VALID_PATH_PREFIX = "/game/"


class ScrapeError(Exception):
    """Base for all scraper errors."""


class ScrapeParseError(ScrapeError):
    """Page fetched but required fields could not be extracted."""


class InvalidPriceChartingURLError(ScrapeError):
    """The URL is not a valid PriceCharting game/product page."""


# ── Scraped result ────────────────────────────────────────────────────────────

@dataclass
class ScrapedCard:
    api_id: str           # "pc_<sha1[:16]>"
    url: str              # canonical URL
    name: str             # e.g. "N's Zekrom #31"
    set_name: str         # e.g. "Pokemon Promo"
    set_code: str         # e.g. "PROMO"
    card_number: str      # e.g. "31"
    image_url: str | None
    prices_available: bool = False
    # USD prices — caller converts to EUR
    price_ungraded: Decimal | None = None   # "Used / Ungraded" — main market value
    price_new: Decimal | None = None        # Sealed / Near-Mint price


# ── URL helpers ───────────────────────────────────────────────────────────────

def canonicalize_url(raw: str) -> str:
    """Normalise a PriceCharting game URL. Raises InvalidPriceChartingURLError if invalid."""
    raw = raw.strip()
    parsed = urlparse(raw)

    if parsed.scheme not in ("http", "https", ""):
        raise InvalidPriceChartingURLError(f"Unexpected URL scheme: {parsed.scheme!r}")

    host = parsed.netloc.lower()
    if "pricecharting.com" not in host:
        raise InvalidPriceChartingURLError("URL is not from pricecharting.com")

    path = parsed.path.rstrip("/")
    if not path.startswith(_VALID_PATH_PREFIX):
        raise InvalidPriceChartingURLError(
            f"URL does not look like a PriceCharting game/product page. "
            f"Expected path starting with {_VALID_PATH_PREFIX!r}, got {path!r}"
        )

    # Ensure exactly two path segments after /game/
    segments = path.lstrip("/").split("/")   # ["game", "set-slug", "card-slug"]
    if len(segments) < 3:
        raise InvalidPriceChartingURLError(
            "URL must include both a set and a card slug, "
            "e.g. /game/pokemon-promo/n%27s-zekrom-31"
        )

    return urlunparse(("https", _VALID_HOST, path, "", "", ""))


def build_api_id(canonical_url: str) -> str:
    """Return a stable 'pc_<16-hex-chars>' identifier."""
    digest = hashlib.sha1(canonical_url.encode()).hexdigest()
    return f"pc_{digest[:16]}"


def _set_slug_to_code(set_slug: str) -> str:
    """Derive a short set code from the URL set slug.

    "pokemon-promo"              → "PROMO"
    "pokemon-black-&-white"      → "BW"
    "pokemon-sword-&-shield"     → "SS"
    "pokemon-japanese-mega-dream-ex" → "JMDE"
    """
    # Strip leading "pokemon-" or "pokemon-japanese-"
    slug = re.sub(r'^pokemon(-japanese)?-', '', set_slug.lower())
    # Remove & and other punctuation, split on hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    words = [w for w in slug.split('-') if w]
    if not words:
        return set_slug.upper()[:8]
    if len(words) == 1:
        return words[0].upper()[:8]
    # Multi-word: first letter of each word
    return ''.join(w[0] for w in words).upper()[:8]


def _extract_set_slug(canonical_url: str) -> str:
    """Return the set slug from the URL path, e.g. 'pokemon-promo'."""
    parts = canonical_url.rstrip("/").split("/")
    # /game/{set-slug}/{card-slug}
    return parts[-2] if len(parts) >= 2 else ""


# ── HTTP fetch ────────────────────────────────────────────────────────────────

async def fetch_html(url: str) -> str:
    """Fetch a PriceCharting product page. Returns HTML on success."""
    try:
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate="chrome124") as session:
            resp = await session.get(
                url,
                headers={"Accept-Language": "en-GB,en;q=0.9"},
                timeout=20,
            )
        html = resp.text
        status = resp.status_code
    except ImportError:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(url)
            html = resp.text
            status = resp.status_code
        except httpx.RequestError as e:
            raise ScrapeError(f"Network error fetching {url}: {e}") from e
    except Exception as e:
        raise ScrapeError(f"Network error fetching {url}: {e}") from e

    if status == 404:
        raise ScrapeParseError(
            f"PriceCharting returned 404 for {url}. "
            "The card may not be in their database yet."
        )
    if status != 200:
        raise ScrapeError(f"PriceCharting returned {status} for {url}")

    return html


# ── Price parser ──────────────────────────────────────────────────────────────

def _parse_usd(text: str) -> Decimal | None:
    """Parse a USD price string like '$9.57' or '$1,234.56' into a Decimal."""
    if not text or text.strip() in ("-", "N/A", ""):
        return None
    cleaned = re.sub(r'[\$,\s]', '', text.strip())
    try:
        val = Decimal(cleaned)
        return val if val > 0 else None
    except InvalidOperation:
        return None


# ── HTML parser ───────────────────────────────────────────────────────────────

def parse_product(html: str, canonical_url: str) -> ScrapedCard:
    """Parse a PriceCharting product page into a ScrapedCard (prices in USD).

    Raises ScrapeParseError if the minimum (name + at least one price)
    cannot be extracted.
    """
    tree = HTMLParser(html)
    api_id = build_api_id(canonical_url)
    set_slug = _extract_set_slug(canonical_url)
    set_code = _set_slug_to_code(set_slug)

    # ── Set name (from breadcrumbs) ──────────────────────────────────
    set_name = set_code
    bc = tree.css_first(".breadcrumbs")
    if bc:
        parts = [p.strip() for p in bc.text(strip=True).split(">") if p.strip()]
        if parts:
            set_name = parts[-1]  # e.g. "Pokemon Promo"

    # ── Card name (h1 minus the appended set name) ───────────────────
    name = ""
    h1 = tree.css_first("h1")
    if h1:
        raw = h1.text(strip=True)
        # h1 = "N's Zekrom #31Pokemon Promo" — set name is appended without a separator
        # Strip the set name from the end (case-insensitive)
        if set_name and raw.lower().endswith(set_name.lower()):
            raw = raw[: -len(set_name)].strip()
        name = raw

    if not name:
        raise ScrapeParseError(
            f"Could not extract card name from {canonical_url}. "
            "Check the URL is a valid PriceCharting product page."
        )

    # ── Card number ──────────────────────────────────────────────────
    # PriceCharting shows it as "#31" in the name
    num_match = re.search(r'#(\w+)', name)
    card_number = num_match.group(1) if num_match else ""

    # ── Image ────────────────────────────────────────────────────────
    image_url: str | None = None
    for img in tree.css("img"):
        src = img.attributes.get("src") or img.attributes.get("data-src") or ""
        alt = img.attributes.get("alt") or ""
        if "pricecharting.com" in src or "storage.googleapis.com" in src:
            if "Prices" in alt or "prices" in alt or name.split("#")[0].strip().lower() in alt.lower():
                image_url = src
                break
    # Fallback: any storage.googleapis link on the page
    if not image_url:
        for img in tree.css("img"):
            src = img.attributes.get("src") or ""
            if "storage.googleapis.com/images.pricecharting.com" in src:
                image_url = src
                break

    # ── Prices ───────────────────────────────────────────────────────
    used_el = tree.css_first("#used_price")
    new_el = tree.css_first("#new_price")

    price_ungraded: Decimal | None = None
    price_new: Decimal | None = None

    if used_el:
        span = used_el.css_first("span.price")
        price_ungraded = _parse_usd(span.text(strip=True) if span else used_el.text(strip=True))

    if new_el:
        span = new_el.css_first("span.price")
        price_new = _parse_usd(span.text(strip=True) if span else new_el.text(strip=True))

    prices_available = price_ungraded is not None or price_new is not None

    if not prices_available:
        raise ScrapeParseError(
            f"Could not extract any prices from {canonical_url}. "
            "The page layout may have changed."
        )

    logger.debug(
        "Scraped PC %s: name=%r set=%r num=%r ungraded=%s new=%s",
        canonical_url, name, set_name, card_number, price_ungraded, price_new,
    )

    return ScrapedCard(
        api_id=api_id,
        url=canonical_url,
        name=name,
        set_name=set_name,
        set_code=set_code,
        card_number=card_number,
        image_url=image_url,
        prices_available=prices_available,
        price_ungraded=price_ungraded,
        price_new=price_new,
    )


# ── Public entry point ────────────────────────────────────────────────────────

async def scrape_card(raw_url: str) -> ScrapedCard:
    """Validate URL, fetch, parse. Raises on any failure."""
    canonical = canonicalize_url(raw_url)
    html = await fetch_html(canonical)
    return parse_product(html, canonical)
