# HANDOVER.md

Complete build log and reference for the PokéTCG Tracker project.

---

## 1. Project Summary

**What it does:** A self-hosted web app for tracking a Pokémon TCG card collection. You log your cards (name, set, variant, condition, purchase price), and the app automatically fetches and caches CardMarket EUR prices via the PokéWallet API. A nightly background job refreshes prices. A portfolio view shows your estimated collection value and historical value chart.

**Stack:**
- Backend: Python 3.12 + FastAPI + SQLAlchemy (async) + APScheduler
- Database: PostgreSQL 16
- Frontend: Vanilla HTML/CSS/JS (no framework, no build step)
- Reverse proxy: Caddy 2
- Containerisation: Docker Compose

**Runs on:** Ubuntu Server, accessible locally at `http://localhost:3003`

**GitHub:** https://github.com/ej22/pokemon-tcg-tracker

---

## 2. Complete Build Log

### Phase 1 — Scaffold
- Created folder structure, `.gitignore`, `.env.example`, `.env`
- Initialised git and created GitHub repo via `gh repo create`
- Branch named `main`

### Phase 2 — Docker Compose and Caddy
- Wrote `docker-compose.yml` with 4 services: `db`, `backend`, `frontend`, `pgadmin`
- All services isolated on a custom Docker network `tcg-net`
- Caddy listens on `:3000` internally (mapped to host `3003`) and proxies `/api/*` to `backend:8000`

### Phase 3 — Database and Alembic
- Wrote SQLAlchemy models for `sets`, `cards`, `collection`, `price_history`, `price_cache`
- Created Alembic structure manually (pip/alembic not available on host; all runs happen inside the container)
- **Problem:** Initial models used `DateTime` (timezone-naive) but the code passes `datetime.now(timezone.utc)` — timezone-aware datetimes. PostgreSQL TIMESTAMP WITHOUT TIME ZONE rejected them.
- **Fix:** Changed all `DateTime` columns to `DateTime(timezone=True)` (maps to `TIMESTAMPTZ`), downgraded and re-ran migration.

### Phase 4 — PokéWallet API Service
- Discovered actual API response structure by inspecting live responses:
  - Card info is nested under `card_info` (not flat)
  - Prices are under `cardmarket.prices[]` with `variant_type`, `avg`, `low`, `trend` fields
  - ID field is `id` (not `productId` or `api_id`)
- Initial `pokewallet.py` assumed flat structure — rewrote with `_normalise_card()` helper that flattens `card_info` for consistent downstream use
- `extract_cardmarket_prices()` reads `cardmarket.prices[]` list directly

### Phase 5 — Routers
- **Problem:** FK violation when adding a card whose `set_id` (e.g. `"2545"`) didn't exist in `sets`. Cards reference sets, but sets are only populated by the `/api/sets` endpoint (which calls the sets API).
- **Fix:** Both `_upsert_card_metadata` in `price_cache.py` and the search router now auto-insert a placeholder `sets` row if the referenced `set_id` is missing, using the `set_name` from the card's own API response. The weekly sets refresh will later fill in the full set data.

### Phase 6 — Frontend
- Single-page hash-based routing (`#collection`, `#portfolio`, `#sets`)
- Dark-mode design with orange accent `#F27E00`
- Chart.js loaded from CDN for portfolio value chart
- Modals for adding and editing collection entries
- Variant dropdown populated from live price API on card selection

### Phase 7 — Verification
- All 4 containers start and pass health checks
- Migrations run cleanly: `alembic upgrade head`
- Search returns correct card data with names, set info, card numbers
- Adding a card triggers one API call (cache miss), stores prices in both `price_history` and `price_cache`
- A second `/api/prices/{id}` call within TTL makes NO new API call (confirmed by absence of "Fetching prices" in logs)
- Portfolio summary returns correct EUR totals
- APScheduler starts with all 4 jobs registered (nightly refresh, weekly sets, hourly/daily counter resets)
- Frontend serves at `http://localhost:3003`
- pgAdmin accessible at `http://localhost:8015`

### Phase 10 — Netflix-style card poster grid + image proxy

**Collection page:** Table replaced with a responsive CSS Grid poster layout (`repeat(auto-fill, minmax(148px, 1fr))`). Each card is a `3:4.2` aspect-ratio portrait poster:
- Card artwork fills the frame (`position: absolute; inset: 0; object-fit: cover`)
- Bottom gradient overlay shows card name, set code, and CardMarket price
- Top-right: condition chip + quantity badge (if qty > 1)
- Top-left: edit and delete action buttons, revealed on hover
- P&L indicator dot (green/red) next to the price
- Clicking the card body opens the existing edit modal
- Graceful placeholder ("P" tile) shown if image fails to load

**Sets page (set detail):** Card-in-set table also replaced with the same poster grid; hover reveals an + Add to Collection button.

**Image proxy (`GET /api/images/{card_api_id}`):** PokéWallet's `/images/{id}` endpoint requires the API key, so the frontend cannot call it directly. A new FastAPI router (`routers/images.py`) proxies the request server-side and returns the JPEG with `Cache-Control: public, max-age=86400`. Browsers cache each image for 24 hours — first page load triggers one API call per card image; subsequent loads are free.

**Image URL format:** The image is retrieved using the card's `api_id` field (the full `pk_...` hash) — no stripping required. The frontend constructs `/api/images/{card.api_id}` and the proxy passes it directly to PokéWallet.

**Migration 0002:** Adds `image_url TEXT` column to `cards` (nullable). Currently unused for images (we construct the URL dynamically), but retained for potential future use if PokéWallet exposes direct CDN URLs.

**CSS key fixes:**
- Poster images and placeholder divs must use `position: absolute; inset: 0` — `height: 100%` does not resolve against a parent whose height is set by `aspect-ratio` alone
- `loading="lazy"` removed from img tags as it suppressed images before layout was computed
- Added `?v=N` version params to CSS/JS `<link>`/`<script>` tags to enable cache-busting on deploy

### Phase 11 — Tracked-sets view + set image proxy

**Motivation:** The sets page previously showed all 700+ sets from PokéWallet. Changed to show only sets the user actually has cards in, so the view is immediately relevant and fast to load.

**Backend — `GET /api/sets/mine`** (`routers/sets.py`):
- New endpoint defined *before* `/{set_id}/cards` to avoid FastAPI routing `mine` as a set_id
- Queries `collection` → `cards` → `sets` join: `SELECT card.set_id, SUM(collection.quantity) AS owned_count … GROUP BY card.set_id`
- Fetches matching `Set` rows and returns `{set_id, set_code, name, language, release_date, card_count, owned_count}` ordered by `release_date DESC`
- Returns `[]` immediately if no sets found (no API call)

**Backend — `GET /api/sets/{set_code}/image`** (`routers/sets.py`):
- Proxies `https://api.pokewallet.io/sets/{set_code}/image` with the server-side API key
- Set identifier accepts either `set_code` (e.g. `JTG`) or numeric `set_id` — both are returned by `/sets/mine`
- Returns the image with `Cache-Control: public, max-age=604800` (7 days, longer than card images since set logos never change)

**Frontend — sets.js rewrite:**
- `loadSets()` now calls `/sets/mine` instead of `/sets`
- `renderSetsGrid(sets)` renders `.poster-card.set-poster` elements; image source is `/api/sets/{set_code}/image`
- `openSetDetail(set)` accepts the full set object (no DOM lookup); renders 12 skeleton placeholders while cards load
- `renderSetCards(cards)` renders portrait poster cards (same as collection view) with + Add button on hover
- `setPlaceholder(label)` shows first 2 chars of set code as text tile if the image fails

**CSS design decisions for set posters:**
- Set logos are ~300×95px landscape images — portrait `3:4.2` ratio used for card posters is wrong for these
- Final solution: `.sets-card-grid` uses `minmax(260px, 1fr)` columns; `.set-poster` uses `aspect-ratio: 16/9` with `object-fit: contain` and `padding: 1.25rem 1.5rem 3rem` so the logo sits in a dark letterbox rather than being stretched
- Cards-within-set view retains the portrait `card-grid` with `minmax(148px, 1fr)` columns and `3:4.2` ratio

**Bugs fixed in this phase:**
1. `#set-detail { display: none }` CSS rule (ID specificity) overrode `classList.remove('hidden')` — JS calls had no effect. Fixed by removing the ID-selector rule entirely and relying solely on the `.hidden` utility class.
2. First attempt at set poster ratio was `aspect-ratio: 3/1` — this collapsed the card to ~50px tall making the logo unreadable. Replaced with `16/9`.
3. `openSetDetail()` was looking up DOM attributes on the clicked element rather than receiving the set object directly — JS serialisation round-trip caused data loss. Fixed by passing the full set object via `onclick`.

### Phase 9 — UI Redesign (dark OLED theme + sidebar layout)

Complete frontend overhaul on the `ui-redesign` branch:

- **Layout:** Single-column stacked views replaced with a persistent left sidebar (`nav.sidebar`) + `main.main-content` layout using CSS Grid
- **Theme:** Replaced ad-hoc dark mode with a full CSS design token system (`--bg-primary`, `--accent`, etc.) targeting OLED-friendly near-black backgrounds (`#0a0a0a`)
- **Typography:** Added Inter (UI) + Fira Code (card IDs/numbers) via Google Fonts; previously system fonts only
- **Navigation:** Sidebar shows active-section highlight and live stats (collection count, portfolio value, sets count) via `updateSidebarStats()`
- **Loading states:** Skeleton shimmer rows replace blank states while data loads (collection table, sets browser)
- **Icons:** Heroicons SVGs replace all emoji icons (edit/delete buttons, nav items)
- **Empty states:** Illustrated empty states added for collection and sets views
- **Toasts:** Multi-toast queue with slide-in animation; previously single toast that overwrote itself
- **Charts:** Chart.js theme updated to match dark tokens (grid lines, tick colours, tooltip background)
- **Chips/badges:** Condition tags, variant badges, and set chips use a unified `.chip` component

Files changed: `frontend/css/style.css` (full rewrite), `frontend/index.html` (full rewrite), `frontend/js/app.js`, `frontend/js/collection.js`, `frontend/js/portfolio.js`, `frontend/js/search.js`, `frontend/js/sets.js`

### Phase 8 — Post-build fixes (sets API field mapping)
Discovered while investigating a missing card (Tyrunt MEP070):

**Problem 1:** `pokewallet.get_sets()` looked for a `results` or `sets` key in the response, but the actual sets API returns `{"success": true, "data": [...]}`. Result: `GET /api/sets` always returned an empty list from the API, so the sets browser never populated.

**Problem 2:** `routers/sets.py` and `scheduler.py` used wrong field names when parsing set objects — `groupId`/`abbreviation`/`publishedOn`/`totalCards` — but the actual API uses `set_id`/`set_code`/`release_date`/`card_count`. Even if data had been fetched, it would have been stored with all null fields.

**Problem 3:** The set-detail endpoint (`GET /sets/{setCode}`) returns `{"success": true, "set": {...}, "cards": [...]}`. The `cards` key was correct but the wrapper handling needed to guard against the disambiguation case (`{"sets": [...]}`) more carefully.

**Fix:** Updated `pokewallet.get_sets()` to check for `data` key first. Updated field mappings in `routers/sets.py` and `scheduler.py` to use the correct API field names. Invalidated existing placeholder sets in the DB (`UPDATE sets SET last_fetched_at = '2000-01-01'`) to force a fresh fetch on next request. After fix, `GET /api/sets` correctly returns all 763 sets including MEP.

**Root cause of missing Tyrunt:** The MEP set ("ME: Mega Evolution Promo", set_code `MEP`, set_id `24451`) exists in PokéWallet's index with 29 listed cards, but only 19 cards are actually in their database. Tyrunt MEP070 is not among them. This is a gap in PokéWallet's data for this newer set (released October 2025) — nothing can be done on our end until they add it.

---

## 3. Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| FastAPI | Async-native, excellent for I/O-bound work (DB + HTTP), auto-generates `/docs` |
| asyncpg driver | Required for async SQLAlchemy with PostgreSQL; psycopg2 is sync-only |
| Alembic (manual) | Versioned, reversible schema migrations; created manually since no local Python env |
| Two price tables | `price_cache` for fast lookups (upsert); `price_history` for time-series charting (append-only) |
| PostgreSQL UPSERT | `INSERT ... ON CONFLICT DO UPDATE` for cache entries — atomic, no race conditions |
| Caddy reverse proxy | Single port for frontend + API; minimal config; handles static file serving |
| Vanilla JS | User preference; no build tools, no dependencies, easy to modify |
| Placeholder sets | Auto-insert when a card references an unknown set_id, to avoid FK violations while sets cache is cold |

---

## 4. Known Issues / Limitations

- **Sets browser on first boot:** visiting `http://localhost:3003/#sets` (or calling `GET /api/sets`) triggers the first fetch of all sets from PokéWallet (~763 sets). This makes one API call and takes a few seconds. After that, sets are cached for 7 days.
- **Rate limit counters are in-memory** — restart resets them. A heavy manual refresh shortly after a restart could momentarily exceed the daily limit before the counter catches up. Low risk in practice given the 1000/day free tier.
- **No authentication** — the app is intended for a private server behind Tailscale. Do not expose port 3003/8014 to the public internet.
- **Price history chart requires 2+ days** of data before it renders. On day one, the chart area shows a "Not enough data" message.
- **Variant matching in portfolio** is best-effort — if a collection entry's `variant` field doesn't exactly match a `price_cache` variant_type, the first cached entry is used as a fallback.
- **pgAdmin `version` warning** in Docker Compose logs — the `version:` key is obsolete in Compose v2 spec. It's cosmetic and doesn't affect function.

---

## 5. How to Resume This Project

### Running it
```bash
git clone https://github.com/ej22/pokemon-tcg-tracker.git
cd pokemon-tcg-tracker
cp .env.example .env    # fill in your values
docker compose up -d
docker compose exec backend alembic upgrade head
open http://localhost:3003
```

### Key files

| File | Role |
|------|------|
| `backend/main.py` | FastAPI app entry point, lifespan (starts/stops scheduler) |
| `backend/models.py` | All SQLAlchemy ORM models |
| `backend/services/pokewallet.py` | All PokéWallet API calls + normalisation |
| `backend/services/price_cache.py` | Cache TTL logic, `get_price()` function |
| `backend/routers/collection.py` | Collection CRUD endpoints |
| `backend/routers/prices.py` | Price fetch and refresh endpoints |
| `backend/routers/portfolio.py` | Portfolio value aggregation |
| `backend/routers/images.py` | Card artwork proxy (adds API key, returns JPEG) |
| `backend/scheduler.py` | APScheduler job definitions |
| `frontend/js/app.js` | Routing, fetch helpers, toast |
| `frontend/js/collection.js` | Collection table + edit modal |
| `frontend/js/search.js` | Search modal + add form |
| `frontend/js/portfolio.js` | Portfolio view + Chart.js |
| `frontend/js/sets.js` | Sets browser + set detail |

### How the cache works
```
GET /api/prices/{id}
  → query price_cache WHERE card_api_id = id
    → if found AND last_fetched_at < 24h ago → return DB data (no API call)
    → else → call PokéWallet /cards/{id}
              → parse cardmarket.prices[]
              → INSERT INTO price_history (append)
              → UPSERT price_cache (overwrite latest)
              → return fresh data
```

### How the scheduler works
APScheduler's `AsyncIOScheduler` starts in FastAPI's `lifespan` context manager. Jobs run in the same async event loop as the web app. Each job opens its own `AsyncSessionLocal()` session — it does NOT share sessions with request handlers.

### Adding new features
- New API endpoint: add a router file in `backend/routers/`, import and `app.include_router()` in `main.py`
- New DB column: add to `models.py`, create a new Alembic migration (`alembic revision --autogenerate -m "desc"`), run `alembic upgrade head`
- New scheduled job: add a function in `scheduler.py`, register it in `start_scheduler()`

---

## 6. Environment Variables Reference

| Variable | Purpose | Safe default |
|----------|---------|-------------|
| `POSTGRES_DB` | Database name | `tcg_tracker` |
| `POSTGRES_USER` | DB user | `tcg_user` |
| `POSTGRES_PASSWORD` | DB password | change this |
| `POKEWALLET_API_KEY` | PokéWallet API key (`pk_live_…`) | required |
| `PRICE_CACHE_TTL_HOURS` | Hours before price is considered stale | `24` |
| `SET_CACHE_TTL_DAYS` | Days before sets list is refreshed | `7` |
| `PGADMIN_EMAIL` | pgAdmin login | `admin@localhost.com` |
| `PGADMIN_PASSWORD` | pgAdmin password | change this |

---

## 7. Port Reference

| Host Port | Container Port | Service | URL |
|-----------|---------------|---------|-----|
| 3003 | 3000 | Caddy (frontend + API proxy) | http://localhost:3003 |
| 8014 | 8000 | FastAPI backend | http://localhost:8014/docs |
| 8015 | 80 | pgAdmin | http://localhost:8015 |
| 5432 | 5432 | PostgreSQL (internal only) | — |

**Confirmed no conflicts with existing services on this server:**

| Port | Existing service | Conflict? |
|------|-----------------|-----------|
| 3000 | carousel-maker | No — mapped to 3003 |
| 3001 | dockhand | No |
| 3002 | cap-web | No |
| 4822 | guacd | No |
| 5000 | postiz | No |
| 7233 | temporal | No |
| 7912 | spoolman | No |
| 8012 | running-route-generator-frontend | No |
| 8013 | temporal-ui | No |
| 8066 | game-tracker | No |
| 8080 | glance | No |
| 8111 | termix | No |
| 8166 | health-charts | No |
| 8969 | spotlight | No |
| 9000–9001 | cap-minio | No |

---

## 8. PokéWallet API Notes

**Base URL:** `https://api.pokewallet.io`  
**Auth:** `X-API-Key` header

**Rate limits (free tier):** ~1,000 calls/day, ~100/hour  
**App limits:** warns at 800/day, stops at 80/hour (leaving headroom)

### Endpoints used

| Endpoint | Used for |
|----------|---------|
| `GET /search?q={query}&limit=20` | Card search in add-card modal |
| `GET /cards/{id}` | Full card detail + prices on cache miss |
| `GET /sets` | Sets list (weekly refresh) |
| `GET /sets/{setCode}` | Cards in a set (on-demand) |

### Response structure (important)

**Sets list** (`GET /sets`):
```json
{ "success": true, "data": [ { "set_id": "24451", "set_code": "MEP", "name": "...", "card_count": 29, "language": "eng", "release_date": "10th October, 2025" }, ... ] }
```

**Set detail** (`GET /sets/{setCode}`):
```json
{ "success": true, "set": { ... }, "cards": [ { "id": "pk_...", "card_info": { ... }, "cardmarket": { ... } }, ... ] }
```

**Card / search results** — card info nested under `card_info`:
```json
{
  "id": "pk_...",
  "card_info": { "name": "...", "set_id": "2545", "set_code": "SWSD", ... },
  "cardmarket": {
    "prices": [
      { "variant_type": "normal", "avg": 14.57, "low": 4, "trend": 14.21 },
      { "variant_type": "holo",   "avg": null,  "low": null, "trend": 16.65 }
    ]
  }
}
```

`_normalise_card()` in `pokewallet.py` flattens the `card_info` structure to a consistent dict used throughout the app.

### Card ID format
IDs are hex hashes prefixed with `pk_` (e.g. `pk_11151dbc98a3...`). There is no separate numeric ID — always use the full `pk_` string as the primary key.

### Disambiguation (sets)
`GET /sets/{setCode}` can return `{"sets": [...]}` when multiple sets match a code. The app detects this (`"sets"` key present, no `"cards"` key) and returns an empty list.

### Data gaps
PokéWallet's database is incomplete for some sets, especially newer releases. A set may appear in the index with a card count but have fewer cards actually available via the API. If a card search returns no results, the card simply hasn't been added to PokéWallet yet.

---

## 9. Database Notes

### Schema overview

```
sets          ← weekly refresh from /sets API
  ↑
cards         ← cached on search/add; auto-placeholder set created if needed
  ↑
collection    ← user's owned cards
price_cache   ← latest price per (card, variant, source); upserted on each fetch
price_history ← all historical prices; appended, never overwritten
```

### Connect manually
```bash
docker compose exec db psql -U tcg_user -d tcg_tracker
```

### Backup
```bash
docker compose exec db pg_dump -U tcg_user tcg_tracker > backup_$(date +%Y%m%d).sql
```

### Restore
```bash
cat backup_20240101.sql | docker compose exec -T db psql -U tcg_user tcg_tracker
```

### Alembic commands
```bash
# Apply migrations
docker compose exec backend alembic upgrade head

# Check current version
docker compose exec backend alembic current

# Create new migration after model changes
docker compose exec backend alembic revision --autogenerate -m "add column foo"

# Rollback one step
docker compose exec backend alembic downgrade -1
```
