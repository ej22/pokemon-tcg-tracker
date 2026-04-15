# Technical Reference — PokéTCG Tracker

Developer documentation for the PokéTCG Tracker. For the user-facing quick-start guide see [README.md](README.md).

---

## Architecture

| Service    | Image                | Role                                      |
|------------|----------------------|-------------------------------------------|
| `db`       | postgres:16-alpine   | PostgreSQL database                       |
| `backend`  | Python 3.12 / FastAPI| REST API, price cache, APScheduler jobs   |
| `frontend` | caddy:2-alpine       | Serves static HTML/JS, proxies `/api/*`   |
| `pgadmin`  | dpage/pgadmin4       | Database admin UI                         |

### Backend layout

```
backend/
  main.py                     FastAPI app + lifespan (starts/stops scheduler)
  database.py                 Async engine + session factory
  models.py                   SQLAlchemy ORM (sets, cards, collection, price_history, price_cache, app_settings)
  schemas.py                  Pydantic request/response models
  scheduler.py                APScheduler jobs (nightly 02:00 price refresh, Sunday 03:00 sets refresh)
  routers/
    auth.py                   POST /api/auth/login, GET /api/auth/status, GET /api/auth/logout
    collection.py             CRUD for user's collection + POST /bulk-missing
    prices.py                 Price fetch + history + manual refresh
    sets.py                   Sets list (weekly-cached) + set cards
    portfolio.py              Portfolio value aggregation
    search.py                 PokéWallet search proxy + card metadata caching
    settings.py               App settings CRUD (pricing_mode, etc.)
    images.py                 Card artwork proxy
    manual_cards.py           POST /api/cards/manual — scrape by PriceCharting URL
  services/
    auth.py                   JWT creation/validation + require_auth() dependency
    pokewallet.py             All PokéWallet HTTP calls + _normalise_card() + extract_cardmarket_prices()
    price_cache.py            Cache TTL logic; get_price() is the single entry point for price data
    pricecharting_scraper.py  PriceCharting HTML scraper (curl_cffi + selectolax)
    currency.py               USD→EUR conversion via Frankfurter/ECB API
```

---

## Prerequisites

- Docker & Docker Compose v2
- A [PokéWallet](https://pokewallet.io) API key
- Ports 3003, 8014, and 8015 free on your server

## Setup

```bash
git clone https://github.com/ej22/pokemon-tcg-tracker.git
cd pokemon-tcg-tracker
cp .env.example .env
# Edit .env — set POKEWALLET_API_KEY and change the default passwords
docker compose up -d
docker compose exec backend alembic upgrade head
open http://localhost:3003
```

---

## Environment Variables

| Variable                | Description                                 | Required | Default  |
|-------------------------|---------------------------------------------|----------|----------|
| `POSTGRES_DB`           | Database name                               | Yes      | —        |
| `POSTGRES_USER`         | Database user                               | Yes      | —        |
| `POSTGRES_PASSWORD`     | Database password                           | Yes      | —        |
| `POKEWALLET_API_KEY`    | Your PokéWallet API key (`pk_live_…`)       | Yes      | —        |
| `PRICE_CACHE_TTL_HOURS` | Hours before a cached price is stale        | No       | `24`     |
| `SET_CACHE_TTL_DAYS`    | Days before the sets list is refreshed      | No       | `7`      |
| `PGADMIN_EMAIL`         | pgAdmin login email                         | Yes      | —        |
| `PGADMIN_PASSWORD`      | pgAdmin login password                      | Yes      | —        |
| `AUTH_USERNAME`         | Login username. Leave unset to disable auth | No       | —        |
| `AUTH_PASSWORD`         | Login password (plaintext or bcrypt hash)   | No       | —        |
| `JWT_SECRET_KEY`        | Secret for signing JWTs. Rotate to invalidate all sessions | No | — |

> **Note:** `docker-compose.yml` passes env vars to the backend via an explicit `environment:` block — variables present in `.env` but not listed there are silently ignored. `AUTH_USERNAME`, `AUTH_PASSWORD`, and `JWT_SECRET_KEY` are all wired up with empty-string fallbacks (`${AUTH_USERNAME:-}`) so omitting them disables auth cleanly.

---

## API Endpoints

| Method | Path                                | Auth required? | Description                                   |
|--------|-------------------------------------|----------------|-----------------------------------------------|
| GET    | `/api/collection`                   | No  | List all collection entries with prices and set metadata. `?for_trade=true` filters to trade-binder entries. |
| POST   | `/api/collection`                   | Yes | Add a card to the collection                  |
| PUT    | `/api/collection/{id}`              | Yes | Update a collection entry                     |
| DELETE | `/api/collection/{id}`              | Yes | Remove a card from the collection             |
| POST   | `/api/collection/bulk-missing`      | Yes | Insert qty=0 placeholders for all uncollected cards in a set (`{set_id}`) |
| POST   | `/api/cards/manual`                 | No  | Scrape and store a card from a PriceCharting URL |
| GET    | `/api/search?q={query}`             | No  | Search for cards via PokéWallet               |
| GET    | `/api/sets`                         | No  | List all cached sets                          |
| GET    | `/api/sets/mine`                    | No  | List only sets the user has tracked cards in  |
| GET    | `/api/sets/{set_id}/cards`          | No  | List cards in a set                           |
| GET    | `/api/sets/{set_code}/image`        | No  | Proxy set logo artwork from PokéWallet        |
| GET    | `/api/prices/{card_api_id}`         | No  | Get latest cached prices for a card           |
| GET    | `/api/prices/{card_api_id}/history` | No  | Full price history for a card                 |
| POST   | `/api/prices/refresh`               | Yes | Force-refresh prices for all collection cards |
| GET    | `/api/portfolio/summary`            | No  | Portfolio value summary                       |
| GET    | `/api/images/{card_api_id}`         | No  | Proxy card artwork from PokéWallet (browser-cacheable) |
| GET    | `/api/settings`                     | No  | Get all app settings as a key→value dict      |
| PUT    | `/api/settings/{key}`               | Yes | Update a setting value                        |
| POST   | `/api/settings/validate-api-key`    | No  | Test the configured `POKEWALLET_API_KEY`; returns `{"status":"valid"}` or `{"status":"invalid","detail":"..."}` |
| POST   | `/api/settings/complete-onboarding` | No  | Save `pricing_mode`, `auto_fetch_full_set`, `set_images`, set `onboarding_complete = "true"`; returns `{"success":true,"grouped_layout":"..."}` |
| POST   | `/api/auth/login`                   | —   | Authenticate with username+password; returns JWT |
| GET    | `/api/auth/status`                  | —   | Returns `{auth_enabled, authenticated}`       |
| GET    | `/api/auth/logout`                  | —   | Informational (JWT is stateless; client deletes token) |
| GET    | `/api/health`                       | No  | Health check                                  |

"Auth required" applies only when `AUTH_USERNAME` is set in the environment. When unset, all endpoints are open and the auth UI is hidden entirely.

Full interactive docs: `http://localhost:8014/docs`

---

## App Settings

Settings are stored in the `app_settings` database table and exposed via `GET/PUT /api/settings`.

| Key | Values | Default | Effect |
|-----|--------|---------|--------|
| `pricing_mode` | `full`, `collection_only` | `full` | Controls whether prices are fetched on card add and nightly refresh |
| `onboarding_complete` | `true`, `false` | `false` (fresh install) / `true` (existing data) | Controls whether the first-boot onboarding wizard is shown on page load |
| `pokewallet_api_key_status` | `valid`, `invalid`, `unknown` | `unknown` | Tracks whether the configured API key has been validated via the wizard |

The `get_pricing_mode(session)` helper in `routers/settings.py` is used internally by `collection.py`, `prices.py`, and `scheduler.py` to gate price-fetching behaviour.

The frontend stores one additional preference in `localStorage` (not the database):

| Key | Values | Default | Effect |
|-----|--------|---------|--------|
| `collectionViewMode` | `flat`, `grouped` | `flat` | Flat poster grid vs grouped-by-set |
| `groupedLayout` | `horizontal`, `grid` | `horizontal` | Horizontal scroll rows vs wrapping grid within set sections |
| `showMissingCards` | `true`, `false` | `true` | Whether qty=0 placeholder cards are visible in the collection |

### Collection entry fields

Each collection entry (`CollectionEntry`) has the following boolean flags in addition to the standard fields:

| Field | Default | Meaning |
|-------|---------|---------|
| `track_price` | `false` | Opt-in price tracking for this card in collection-only mode |
| `for_trade` | `false` | Card is listed in the Trade Binder; always has pricing enabled |
| `quantity = 0` | — | Missing/wanted placeholder; excluded from portfolio totals and sidebar count |

Price-fetching logic at a glance:
- `quantity = 0` → never fetch
- `for_trade = true` → always fetch (regardless of `pricing_mode`)
- `track_price = true` + `pricing_mode = collection_only` → fetch
- `pricing_mode = full` → always fetch

---

## UI

The frontend is a single-page vanilla HTML/JS/CSS app served by Caddy — no build step, no framework.

**Collection view** — Netflix-style poster grid. Each card shows artwork, condition chip, quantity badge, and price overlay. In full pricing mode, a P&L dot indicates gain/loss vs purchase price. Hover reveals edit/delete buttons. Touch devices use tap-to-reveal. The view can be switched to grouped-by-set mode using the toggle button in the page header.

**Grouped view** — Cards organised into collapsible sections per set. Each section header shows the set name, owned/total card count, and (in full mode) the set's EUR value. Sections can be set to horizontal scroll rows (default) or a wrapping grid via Settings. Collapse state persists in `localStorage`.

**Settings modal** — Gear icon in the sidebar footer (desktop), topbar (tablet 601–1023px), or a dedicated fixed button in the top-right corner (phone portrait ≤600px — `btn-settings-mobile`, `position: fixed; top: 0.75rem; right: 0.75rem`). Controls pricing mode and grouped layout. Switching to full pricing mode shows a warning about API rate limits.

**Portfolio view** — KPI summary (estimated value, total cards, unique cards, priced count) and a Chart.js line chart of portfolio value over time, plus a value-by-set breakdown table. Hidden in collection-only mode with a prompt to enable pricing.

**Sets view** — Landscape poster grid of sets the user has cards in. Clicking a set loads its cards as a portrait poster grid with an Add to Collection button on hover. A "Track all missing" button inserts qty=0 placeholders for every uncollected card in the set.

**Trade Binder view** — Filtered collection view showing only cards marked `for_trade=true`. Always shows CardMarket prices regardless of `pricing_mode`. Summary bar displays card count and total estimated value. Cards can be removed from the binder via the trade toggle button.

**Missing cards** — Qty=0 placeholder entries render with a grayscale image and a "Missing" badge. They are hidden from the sidebar card count but shown in a separate "Missing" stat row. A "Show/Hide missing" toggle in the collection page header controls visibility (state persisted in `localStorage`).

**Authentication** — When `AUTH_USERNAME` is set in the environment, a login modal appears the first time any write action is attempted. Subsequent requests in the same session use a JWT stored in `localStorage`. The sidebar shows the logged-in username and a sign-out button. When `AUTH_USERNAME` is not set, the auth UI is completely hidden and all endpoints are open (backward-compatible default).

**Image proxy** — Card artwork is served via `GET /api/images/{card_api_id}` with `Cache-Control: public, max-age=86400`. Set logos via `GET /api/sets/{code}/image` with 7-day cache.

**Card view lightbox** — Clicking a card in the collection opens a full-screen overlay (`#card-view-overlay`) showing the card artwork at a larger scale alongside card metadata (name, set, number, condition, quantity), a price row, and a purchase/P&L summary. An "Edit entry" button in the panel opens the edit modal. On mobile the panel is portrait-stacked; on desktop it is a side-by-side panel (max-width 900px) with the artwork up to 380px wide. Idea credited to @Awesmoe on GitHub. Hover zoom scaling was removed at the same time to prevent card art being clipped at the edges.

**Mobile layout** — Sidebar on desktop (>1023px). Compact topbar on tablets (601–1023px). Fixed bottom nav on phones (≤600px); topbar hidden. Settings gear on phones is a separate `position: fixed` button (`btn-settings-mobile`) in the top-right corner — it never affects document flow. Touch targets 44px minimum. iOS safe-area inset handled on bottom nav. The edit modal uses `svh` (small viewport height) so it does not resize when the soft keyboard opens; the form body scrolls independently and the Save button is `position: sticky; bottom: 0` so it remains reachable without scrolling.

---

## How the Price Cache Works

Prices are fetched from CardMarket (EUR) via PokéWallet and stored in two tables:

- **`price_cache`** — one row per (card, variant, source), upserted on each fetch. Fast lookups.
- **`price_history`** — every fetch appended as a new row, never overwritten. Historical charting.

```
get_price(card_api_id)
  → check price_cache table
  → if fresh (< PRICE_CACHE_TTL_HOURS, default 24h) → return DB data (no API call)
  → else → branch on card.source:
      "pokewallet"           → GET /cards/{id} → parse cardmarket.prices[]
      "pricecharting_scrape" → scrape PriceCharting HTML → convert USD→EUR
    → INSERT INTO price_history (append)
    → UPSERT price_cache (latest value)
```

Price fetching is gated on `pricing_mode`. When `collection_only`, `get_price()` is never called from `add_to_collection`, the nightly scheduler exits early, and `POST /prices/refresh` returns a disabled message.

### Rate limit protection

PokéWallet free tier: ~1,000 calls/day, ~100/hour. The backend warns at 800/day and stops at 80/hour, resetting counters on schedule. Counters are in-memory — restart resets them.

---

## PriceCharting Fallback

For cards missing from PokéWallet (promos, newer sets):

1. Find the card on [PriceCharting.com](https://www.pricecharting.com) and copy its URL.
2. In the Add Card modal, click **Add by PriceCharting URL**.
3. Paste the URL and click Fetch.

Cards are scraped via `curl_cffi` (Chrome TLS impersonation) + `selectolax` and stored with a `pc_`-prefixed synthetic ID. Prices are converted from USD to EUR via the ECB rate (Frankfurter API, 24-hour cache, `0.92` fallback). The nightly job re-scrapes these cards (capped at 60/night, 2–4 s throttle).

Collection badges: **PC** for PriceCharting-sourced cards; **Stale** if price data exceeds the cache TTL.

---

## Scheduled Jobs

| Job                    | Schedule           | What it does                                                      |
|------------------------|--------------------|-------------------------------------------------------------------|
| Nightly price refresh  | Every day at 02:00 | Refreshes PokéWallet prices then re-scrapes PriceCharting cards. In collection-only mode, refreshes only entries with `track_price=true` or `for_trade=true` (qty > 0); skips entirely if none exist. |
| Weekly sets refresh    | Sundays at 03:00   | Re-fetches the full sets list from PokéWallet                     |
| Hourly counter reset   | Every hour :00     | Resets the hourly API call counter                                |
| Daily counter reset    | Every day at 00:00 | Resets the daily API call counter                                 |

The nightly job checks `pricing_mode` at the start and returns immediately if `collection_only`.

---

## Alembic Migrations

```bash
# Apply all pending migrations
docker compose exec backend alembic upgrade head

# Check current revision
docker compose exec backend alembic current

# Create a new migration after model changes
docker compose exec backend alembic revision --autogenerate -m "description"

# Rollback one step
docker compose exec backend alembic downgrade -1
```

Migrations live in `backend/alembic/versions/`. When a new migration is generated inside the container, copy it to the host:

```bash
docker compose cp backend:/app/alembic/versions/<file>.py backend/alembic/versions/
```

---

## Database

### Schema

```
app_settings  ← key/value store for app-level config (e.g. pricing_mode)
sets          ← weekly refresh from /sets API
  ↑
cards         ← cached on search/add; auto-placeholder set created if needed
  ↑
collection    ← user's owned cards
price_cache   ← latest price per (card, variant, source); upserted on each fetch
price_history ← all historical prices; appended, never overwritten
```

### Useful commands

```bash
# Connect
docker compose exec db psql -U tcg_user -d tcg_tracker

# Backup
docker compose exec db pg_dump -U tcg_user tcg_tracker > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20240101.sql | docker compose exec -T db psql -U tcg_user tcg_tracker
```

---

## Adding new features

- **New API endpoint:** add a router file in `backend/routers/`, import and `app.include_router()` in `main.py`
- **New DB column:** add to `models.py`, generate an Alembic migration, run `alembic upgrade head`
- **New scheduled job:** add a function in `scheduler.py`, register it in `start_scheduler()`
- **New app setting:** add a row to the `app_settings` seed in the migration, add to `_VALID_VALUES` in `routers/settings.py`, handle in `applySettingsToUI()` in `frontend/js/app.js`

---

## Port Reference

| Host Port | Service | URL |
|-----------|---------|-----|
| 3003 | Frontend (Caddy) | http://localhost:3003 |
| 8014 | Backend (FastAPI) | http://localhost:8014/docs |
| 8015 | pgAdmin | http://localhost:8015 |

---

## PokéWallet API Notes

**Base URL:** `https://api.pokewallet.io`  
**Auth:** `X-API-Key` header  
**Rate limits (free tier):** ~1,000 calls/day, ~100/hour

### Response structure

**Card / search results** — card info nested under `card_info`:
```json
{
  "id": "pk_...",
  "card_info": { "name": "...", "set_id": "2545", "set_code": "SWSD", ... },
  "cardmarket": {
    "prices": [
      { "variant_type": "normal", "avg": 14.57, "low": 4, "trend": 14.21 }
    ]
  }
}
```

`_normalise_card()` in `pokewallet.py` flattens this. Always use normalised data downstream.

**Sets list** (`GET /sets`): `{ "success": true, "data": [ { "set_id": "...", "set_code": "...", ... } ] }`

**Set detail** (`GET /sets/{setCode}`): `{ "success": true, "set": {...}, "cards": [...] }` — can also return `{"sets": [...]}` for ambiguous codes; the app detects this and returns an empty list.

### Card ID format
IDs are hex hashes prefixed with `pk_`. Always use the full string as the primary key. PriceCharting-scraped cards use `pc_` prefix with a SHA-1 hash of the canonical URL.

---

## Known Issues / Limitations

- **Sets browser on first boot:** `GET /api/sets` triggers a fetch of all sets (~763). Takes a few seconds; cached for 7 days after that.
- **Rate limit counters are in-memory** — restart resets them. Low risk in practice.
- **Authentication is optional** — disabled by default (omit `AUTH_USERNAME`). When enabled, JWT tokens are stored in `localStorage`; rotating `JWT_SECRET_KEY` invalidates all active sessions. Suitable for self-hosting; still not recommended to expose directly to the public internet without a reverse proxy with TLS.
- **PriceCharting scraping** — currently reliable, but could break if PriceCharting adds bot protection. On failure, the last cached price is retained and a Stale badge appears.
- **PriceCharting prices are USD** — converted at fetch time. Fallback rate `0.92` used if Frankfurter is unreachable.
- **Portfolio chart requires 2+ days** of price history before it renders.
- **Variant matching** in portfolio is best-effort — falls back to first cached variant if no exact match.
