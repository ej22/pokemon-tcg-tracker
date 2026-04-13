# Technical Reference

Current system state as of Phase 24. For the full build log see HANDOVER.md.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), Alembic |
| Database | PostgreSQL 16 (asyncpg driver) |
| Frontend | Vanilla HTML/CSS/JS — no build step |
| Reverse proxy | Caddy 2 (static files + `/api/*` proxy) |
| Containers | Docker Compose (4 services on `tcg-net` bridge) |
| Scheduler | APScheduler `AsyncIOScheduler` (runs inside FastAPI lifespan) |

---

## Services & Ports

| Host port | Service | URL |
|-----------|---------|-----|
| 3003 | Caddy (frontend + API) | http://localhost:3003 |
| 8014 | FastAPI (Swagger UI) | http://localhost:8014/docs |
| 8015 | pgAdmin | http://localhost:8015 |
| 5432 | PostgreSQL (internal only) | — |

---

## Database Schema

```
sets          set_id PK, set_code, name, language, release_date, card_count, last_fetched_at
cards         api_id PK, name, clean_name, set_id FK→sets, set_code, card_number,
              rarity, card_type, hp, stage, image_url, source, source_url, last_fetched_at
collection    id PK, card_api_id FK→cards, quantity (0=missing placeholder), condition,
              language, variant, purchase_price, purchase_currency, date_acquired, notes,
              track_price, for_trade, created_at
price_cache   id PK, card_api_id FK→cards, variant_type, avg_price, low_price,
              trend_price, market_price, currency, source, last_fetched_at
price_history id PK, card_api_id FK→cards, variant_type, avg_price, low_price,
              trend_price, market_price, currency, source, fetched_at
app_settings  key PK, value, updated_at
```

Key rules:
- `collection.quantity = 0` → missing/wanted placeholder (excluded from portfolio value, price refresh)
- `cards.source` = `"pokewallet"` or `"pricecharting_scrape"`
- When a card is cached before its set exists, a placeholder `sets` row is auto-inserted; the weekly sets refresh fills it in later

---

## API Endpoints

### Sets
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/sets` | All sets (weekly-cached from PokéWallet) |
| GET | `/api/sets/mine` | Sets the user has collection entries in, with `owned_count` |
| GET | `/api/sets/{set_id}/cards` | All cards in a set. Fetches from API if cache is incomplete AND `auto_fetch_full_set` is enabled; otherwise serves from DB. Returns `CardOut + owned_quantity` |
| GET | `/api/sets/{set_code}/image` | Set artwork proxy (7-day browser cache) |

### Collection
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/collection` | All entries with enriched card + price data. `?for_trade=true` filters to trade cards |
| POST | `/api/collection` | Add entry. qty=0 skips price fetch; otherwise gated on pricing_mode/flags |
| PUT | `/api/collection/{id}` | Update entry. Triggers price fetch if track_price/for_trade toggled on |
| DELETE | `/api/collection/{id}` | Remove entry |
| POST | `/api/collection/bulk-missing` | Add qty=0 placeholders for all uncached cards in a set (`{set_id}`) |

### Prices
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/prices/{card_api_id}` | Latest cached prices for a card |
| POST | `/api/prices/refresh` | Manual price refresh (gated on pricing_mode) |

### Search & Cards
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/search?q=...` | PokéWallet search proxy |
| POST | `/api/cards/manual` | Add card by PriceCharting URL (for promos missing from PokéWallet) |

### Images
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/images/{card_api_id}` | Card artwork. Served from disk cache (`./image_cache/`) on hit; fetches from PokéWallet or Google CDN on miss and caches to disk. Each image costs 1 API call ever. 7-day browser cache. |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio/summary` | Total value, cost, P&L |
| GET | `/api/portfolio/history` | Time-series value data for chart |

### Settings & Auth
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings` | All settings as `{key: value}` |
| PUT | `/api/settings/{key}` | Update a setting. Valid keys: `pricing_mode` (`"full"`/`"collection_only"`), `auto_fetch_full_set` (`"enabled"`/`"disabled"`), `set_images` (`"visible"`/`"hidden"`) |
| POST | `/api/auth/login` | Returns JWT token |
| GET | `/api/auth/status` | `{auth_enabled, authenticated}` |
| GET | `/api/auth/logout` | Informational (JWT is stateless) |

---

## Scheduled Jobs

| Job | Schedule | Purpose |
|-----|----------|---------|
| `nightly_price_refresh` | Daily 02:00 | Refresh prices for all collection cards (full mode) or track_price/for_trade cards (collection_only mode) |
| `backfill_incomplete_sets` | Hourly :05 | Fill sets whose DB card count < `card_count`. Only runs when `auto_fetch_full_set` is enabled. Only processes sets in the user's collection. Stops if hourly API limit is hit; resumes next hour |
| `weekly_sets_refresh` | Sunday 03:00 | Refresh the sets index from PokéWallet |
| `reset_hourly_counter` | Hourly :00 | Reset PokéWallet hourly call counter |
| `reset_daily_counter` | Daily 00:00 | Reset PokéWallet daily call counter |

---

## PokéWallet API

**Base URL:** `https://api.pokewallet.io`  
**Auth:** `X-API-Key` header  
**Rate limits:** ~1,000/day, ~100/hour (app warns at 800/day, stops at 80/hour)

**429 handling:** All four API functions check for HTTP 429 and return `[]`/`None` instead of raising. The internal hourly counter resets on container restart so it may not reflect the real server quota — the 429 check is the safety net for that gap. Set detail degrades gracefully to serving cached DB cards when rate-limited.

### Image disk cache

Images are stored at `./image_cache/` (bind-mounted into the container):
- `{card_api_id}` — raw image bytes
- `{card_api_id}.ct` — content-type sidecar (e.g. `image/jpeg`)

Each image is fetched from upstream exactly once ever; all subsequent requests are served from disk. Override path with `IMAGE_CACHE_DIR` env var.

**Backup:** `tar -czf image_cache_backup.tar.gz image_cache/`

### Response shapes

**Card (search / `/cards/{id}`)** — card info is nested:
```json
{
  "id": "pk_...",
  "card_info": { "name": "...", "set_id": "2545", "set_code": "JTG", "card_number": "001", ... },
  "cardmarket": { "prices": [{ "variant_type": "normal", "avg": 14.57, "trend": 14.21 }] }
}
```
`pokewallet._normalise_card()` flattens this — always use normalised data downstream.

**Sets list** (`GET /sets`):
```json
{ "success": true, "data": [{ "set_id": "...", "set_code": "JTG", "name": "Journey Together", "card_count": 335, ... }] }
```

**Set detail** (`GET /sets/{setCode}`):
```json
{ "success": true, "set": { ... }, "cards": [{ "id": "pk_...", "card_info": { ... }, ... }] }
```
Disambiguation case (multiple sets matched): `{"sets": [...]}` with no `"cards"` key — app returns `[]`.

---

## Frontend

**Routing:** Hash-based (`#collection`, `#portfolio`, `#sets`, `#trade-binder`). `showView()` in `app.js` calls the appropriate `load*()` function.

**JS files:**

| File | Responsibility |
|------|---------------|
| `app.js` | Routing, `apiFetch()`, toasts, settings modal, auth modal, `requireAuth()`, sidebar stats |
| `collection.js` | Poster grid, grouped-by-set view, collapsible sections, card-view lightbox, edit/delete |
| `search.js` | Search modal, add-card form, PriceCharting URL flow |
| `sets.js` | Sets grid, set detail, `renderSetCards()` with owned/unowned styling, "Track all missing" |
| `portfolio.js` | KPIs, Chart.js value history |
| `trade-binder.js` | Trade binder view (filtered to `for_trade=true` cards) |

**Key patterns:**
- `apiFetch(path, options)` — wrapper that adds auth header, handles 401 retry, and throws on non-2xx
- `requireAuth()` — returns immediately if token valid; otherwise shows login modal and queues a Promise
- `poster-card--missing` CSS class — grayscale(0.85) + opacity 0.5 on image; opacity 0.5 on overlay. Used for both zero-quantity collection placeholders and unowned cards in set detail
- Cache-busting: `?v=N` suffix on all JS/CSS `<script>`/`<link>` tags — bump `N` whenever frontend files change

**Pricing mode (`window.appSettings.pricing_mode`):**
- `"full"` — prices shown everywhere, fetched on add/update
- `"collection_only"` — prices only for cards with `track_price=true` or `for_trade=true`

---

## Auth

Optional JWT auth. Enabled by setting `AUTH_USERNAME` + `AUTH_PASSWORD` + `JWT_SECRET_KEY` in `.env`. When unset, all endpoints are public (intended for private network / Tailscale deployment).

Write endpoints protected: `POST/PUT/DELETE /collection`, `POST /collection/bulk-missing`, `PUT /settings/{key}`, `POST /prices/refresh`.

---

## Price Sources

| Source | `cards.source` value | Price currency | Notes |
|--------|---------------------|---------------|-------|
| PokéWallet / CardMarket | `"pokewallet"` | EUR | Primary source for all standard cards |
| PriceCharting scrape | `"pricecharting_scrape"` | USD→EUR | For promo cards missing from PokéWallet. Image served from Google Storage CDN |

PriceCharting USD prices converted at fetch time via `api.frankfurter.app` (ECB rate, 24h in-memory cache, fallback `0.92`).

---

## Common Operations

```bash
# Rebuild backend after code changes
docker compose up -d --build backend

# Run / check migrations
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current

# Create a new migration after model changes
docker compose exec backend alembic revision --autogenerate -m "description"

# Tail backend logs
docker compose logs -f backend

# Connect to DB
docker compose exec db psql -U tcg_user -d tcg_tracker

# Backup DB
docker compose exec db pg_dump -U tcg_user tcg_tracker > backup_$(date +%Y%m%d).sql
```
