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

### Phase 12 — Mobile responsive layout

**Motivation:** The app had a basic `@media (max-width: 1023px)` breakpoint that showed a top bar with text-only nav links, but at ≤600px the nav links became completely blank (icons were `display: none`, text was hidden by a second rule). Edit/delete/add buttons on poster cards were hover-only and therefore inaccessible on touch. Tested on an iPhone 16e.

**Navigation:**
- At ≤600px: top bar hidden entirely; a fixed `<nav class="bottom-nav">` bar replaces it. Three tabs (Collection, Portfolio, Sets) each show a 22px icon above a small label. Uses the same `.nav-link[data-view]` pattern the existing JS routing already queries — no JS changes needed.
- At 601–1023px (tablets): top bar retained; nav links redesigned to show icon + stacked label (was text-only).
- The bottom nav uses `position: fixed; bottom: 0` with `transform: translateZ(0)` for iOS compositing stability.

**iOS safe area fix (critical):**
The bottom nav was initially `height: 60px` with `padding-bottom: env(safe-area-inset-bottom)`. This meant the bar's background only covered 60px — the home indicator zone (~34px on iPhone 16e) was below the background, causing page content to bleed through during scroll. Fixed by:
```css
height: calc(var(--bottom-nav-h) + env(safe-area-inset-bottom, 0px));
padding-bottom: env(safe-area-inset-bottom, 0px);
```
The bar now grows to ~94px on iPhone, its background covers the full home indicator area, and icons sit in the upper 60px portion.

**Poster card actions on touch:**
```css
@media (hover: none) {
  .poster-actions { opacity: 1; transform: none; }
  .poster-action-btn { width: 32px; height: 32px; }
}
```
Edit/delete/add buttons are always visible on touch devices instead of requiring a CSS hover.

**Other mobile fixes:**
- Sets grid: `1fr` on phones (was `repeat(2, 1fr)` — at ~160px wide, 16:9 cards were ~90px tall and logos were unreadable)
- Touch targets: `.input { min-height: 44px }`, `.btn { min-height: 44px }`, `.btn-sm { min-height: 36px }`
- Toast container repositioned to `bottom: calc(var(--bottom-nav-h) + 0.75rem)` so it clears the bottom nav
- `main-content` gets `padding-bottom: calc(var(--bottom-nav-h) + env(safe-area-inset-bottom, 0px))` so content doesn't hide behind the bar
- CSS cache-buster bumped to `?v=10`

### Phase 13 — Tap-to-reveal poster card actions (touch)

**Problem:** After Phase 12, poster card action buttons (edit/delete on collection cards, Add on set-detail cards) were always visible on touch devices via `@media (hover: none) { .poster-actions { opacity: 1 } }`. This looked cluttered and was aesthetically poor.

**Solution:** Tap-to-reveal with a `.tapped` CSS class:

- `@media (hover: none)` rule changed to target `.poster-card.tapped .poster-actions` instead of `.poster-actions` directly — actions are hidden by default and only shown when `.tapped` is present.
- **First tap** on a card: JS adds `.tapped` to that card (removing it from any other), revealing the action buttons. The edit modal does NOT open.
- **Tap an action button**: fires immediately (delete or edit). `stopPropagation()` on the `.poster-actions` wrapper prevents the card-level handler from also firing.
- **Second tap** on the same card body (already `.tapped`): removes `.tapped` and opens the edit modal.
- **Tap outside any card**: a `document`-level click listener removes `.tapped` from all cards.
- **Desktop unchanged**: hover reveals buttons, single click opens modal — no `.tapped` logic runs when `(hover: hover)`.

**Implementation:**
- `collection.js`: removed inline `onclick`/`onkeydown` from card div; added `data-entry="${entryJson}"` attribute; delegated click listener on `collectionGrid` handles tap toggle + modal open; `openEditModal()` clears `.tapped` before opening.
- `sets.js`: same delegated listener on `setCardsGrid` for `.set-poster-card` tap toggle (Add button only, no second-tap action needed).
- `app.js`: document-level `click` listener — if click target is not inside `.poster-card`, remove `.tapped` from all cards.
- CSS/JS cache-buster bumped to `?v=11`.

### Phase 14 — PriceCharting scraping for promo cards missing from PokéWallet

**Motivation:** PokéWallet's database is incomplete for some promo cards (e.g. Black Star Promos shipped in ETBs, like *N's Zekrom V1 MEP031*). These cards exist and have prices on [PriceCharting.com](https://www.pricecharting.com) but cannot be found via search. The feature lets users paste a PriceCharting product URL to add any missing card.

**Scraper — `backend/services/pricecharting_scraper.py`:**
- `canonicalize_url(raw)`: validates the URL is a `pricecharting.com/game/{set}/{card}` product page; raises `InvalidPriceChartingURLError` otherwise.
- `build_api_id(url)`: returns `f"pc_{sha1(canonical)[:16]}"` — a synthetic primary key that fits the existing `String` PK schema.
- `fetch_html(url)`: uses `curl_cffi` with Chrome 124 TLS impersonation to avoid bot detection; falls back to `httpx` if `curl_cffi` is unavailable.
- `parse_product(html, url)`: extracts name (strips set suffix from h1), set name (breadcrumb), card number (regex on name), image URL (Google Storage CDN `img`), and USD prices from `#used_price` / `#new_price` DOM IDs.
- Returns a `ScrapedCard` dataclass. Raises `ScrapeParseError` if name or price are missing.

**Currency service — `backend/services/currency.py`:**
- Fetches USD→EUR rate from `api.frankfurter.app` (ECB data, no API key).
- 24-hour in-memory cache with `Decimal("0.92")` fallback if the API is unreachable.

**Schema changes (migrations 0003 + 0004):**
- `cards.source` (NOT NULL, default `"pokewallet"`) — discriminator: `"pokewallet"` or `"pricecharting_scrape"`.
- `cards.source_url` (nullable TEXT) — stores the PriceCharting URL for scraped cards.
- Scraped cards use a `pc_{set_code}` placeholder `sets` row (same pattern as PokéWallet placeholder sets).

**Price pipeline — `backend/services/price_cache.py`:**
- `scrape_and_store(session, url, force_refresh)`: validates URL, checks cache freshness, scrapes, converts USD→EUR, upserts card + prices.
- `get_price()` branches on `card.source == "pricecharting_scrape"` to call the scraper path instead of PokéWallet.
- Price mapping: `avg_price` + `market_price` ← ungraded EUR; `trend_price` ← new/mint EUR; `source = "pricecharting_scrape"`.

**New endpoint — `POST /api/cards/manual`** (`backend/routers/manual_cards.py`):
- Accepts `{"url": "https://www.pricecharting.com/..."}`.
- Returns a card shape (api_id, name, set_name, set_code, card_number, image_url, source, source_url) compatible with the existing add-to-collection flow.
- Error handling: 422 for invalid/unparseable URLs, 502 for network failures.

**Image proxy update — `backend/routers/images.py`:**
- If `card.source == "pricecharting_scrape"`, fetches `card.image_url` directly from Google Storage CDN (no PokéWallet API key needed).
- Falls through to the PokéWallet proxy path for all other cards.

**Nightly scheduler update — `backend/scheduler.py`:**
- Phase 2 added after the PokéWallet loop: queries cards with `source == "pricecharting_scrape"`, refreshes them with `asyncio.sleep(random.uniform(2.0, 4.0))` throttle between requests, capped at 60 per night.

**Frontend:**
- Add Card modal: "Card not found on PokéWallet?" small link replaced with a full-width secondary button **Add by PriceCharting URL**; subtitle "For promo cards not found in PokéWallet".
- URL step: input + Fetch button; error display below; "← Back to search" link.
- Collection poster: **PC** chip badge for `source === "pricecharting_scrape"` cards; **Stale** chip if `last_fetched_at` exceeds TTL.
- `bestPrice()` and `isPriceStale()` filters updated to include `"pricecharting_scrape"` source.
- CSS/JS cache-buster bumped to `?v=14`.

**Dependencies added:**
- `selectolax==0.3.21` — fast HTML parser
- `curl_cffi==0.7.4` — Chrome TLS impersonation for bot-resistant scraping

**Smoke test result (N's Zekrom #31):**
```
POST /api/cards/manual {"url":"https://www.pricecharting.com/game/pokemon-promo/n%27s-zekrom-31"}
→ api_id: pc_a876624e3899bfdf, name: "N's Zekrom #31", set_code: PROMO
   avg=8.80 market=8.80 trend=10.58 currency=EUR
```

---

### Phase 15 — Pricing mode toggle (collection-only mode)

**Motivation:** Users who want to track what they own without consuming PokéWallet API quota needed a way to disable all price fetching. The pricing integration is deep but its touch points are well-defined.

**New model — `AppSetting` (`backend/models.py`):**
- Key-value settings table: `key` (PK), `value`, `updated_at`.
- Migration `c17d2f173cf7` creates the table and seeds `pricing_mode = 'full'` for existing deployments.

**New router — `backend/routers/settings.py`:**
- `GET /api/settings` — returns all settings as a flat `{key: value}` dict.
- `PUT /api/settings/{key}` — validates known keys (`pricing_mode` accepts `"full"` or `"collection_only"`) then upserts.
- `get_pricing_mode(session)` — async helper used internally; returns `"full"` if no row exists (safe default).

**Backend gating — three touch points:**
1. `add_to_collection` (`routers/collection.py`) — `await get_price(...)` wrapped in `if pricing_mode == "full"`.
2. `nightly_price_refresh` (`scheduler.py`) — checks mode at the start and returns early if `"collection_only"`. The job still fires on schedule so toggling back to full mode resumes immediately the next night.
3. `manual_refresh` (`routers/prices.py`) — returns `{"message": "Pricing is disabled..."}` without fetching.

**`_enrich_entry` update (`routers/collection.py`):**
- Now also loads the `Set` row for each card and injects `set_name` and `set_card_count` into the card dict. Used by the grouped view for section headers and completion counts. Schema: `set_name: Optional[str] = None`, `set_card_count: Optional[int] = None` added to `CardOut`.

**Frontend — settings modal:**
- Gear icon button added to `.sidebar-footer` (desktop) and `.topbar` (tablet/mobile).
- `#settings-modal-overlay` follows the existing modal pattern.
- Mode toggle: two-button pill ("Full" / "Collection only"). Active state highlighted with accent colour.
- Description card updates to explain the active mode.
- Warning banner shown when switching TO full mode: explains API quota implications.
- `loadSettings()` in `app.js` calls `GET /api/settings` and stores result in `window.appSettings`. Called before `routeFromHash()` on `DOMContentLoaded` so the mode is known before any view renders.
- `applySettingsToUI()` hides the "Est. value" sidebar stat and layout toggle buttons based on mode.

**Frontend — conditional rendering:**
- `collection.js`: `renderPosterCard()` factored out of the map loop. Checks `window.appSettings.pricing_mode`; in `collection_only` mode skips `bestPrice()`, omits price row, P&L dot, and stale/PC badges.
- `portfolio.js`: `loadPortfolio()` checks mode first. In `collection_only` mode shows `#portfolio-disabled` div (with "Open Settings" button) instead of loading KPIs/chart. Hides "Refresh prices" button.
- `app.js`: "Est. value" sidebar stat row hidden in `collection_only` mode.

---

### Phase 16 — Collection grouped by set with collapsible sections

**Motivation:** Users want to see their collection organised by set, with the ability to collapse sets they're done with. Especially useful in collection-only mode for tracking set completion progress.

**View toggle:**
- Toggle button (list/grid icon) added to the collection page-actions bar. State stored in `localStorage` as `collectionViewMode` (`flat` or `grouped`).
- When switching modes, `collectionGrid`'s class is swapped: `card-grid` for flat mode, `set-group-stack` for grouped mode. This was the critical fix — leaving `card-grid` on the outer container caused set groups to be placed into grid cells, making sections appear side by side as a single row instead of stacking vertically.

**Grouped rendering — `renderCollectionGrouped(entries, pricingOn)` (`collection.js`):**
- Groups entries by `card.set_id`. Entries without a set_id go under key `"__other__"` (displayed as "Other").
- Groups sorted alphabetically by set name.
- Each group renders as `.set-group` with a collapsible header + body.
- Header shows: chevron, set name, owned/total count (`12 / 198 cards`), and EUR value (full mode only).
- Collapse state persists per set in `localStorage` (`setGroup_{setId}`).
- Delegated click handler on headers toggles `.collapsed` class and `aria-expanded`.

**Layout setting:**
- `grouped_layout` stored in `localStorage` (`horizontal` default, `grid` alternative).
- Surfaced in the settings modal as a second toggle row ("Horizontal" / "Grid"), separated from pricing mode by a `.settings-divider`.
- In `renderCollectionGrouped`, the body element gets class `set-group-row` (horizontal) or `card-grid` (grid) based on the setting.
- `window.appSettings.grouped_layout` is read at render time; changing the setting in the modal triggers an immediate re-render if currently in grouped view.

**Horizontal scroll rows (`.set-group-row`):**
- `display: flex; overflow-x: auto; scroll-snap-type: x proximity`.
- Poster cards fixed at `width: 148px; flex-shrink: 0` to prevent them from stretching.
- Thin styled scrollbar (4px height) visible on desktop.

**CSS structure:**
- `.set-group-stack` — vertical flex column with `0.5rem` gap. Applied to `#collection-grid` in grouped mode.
- `.set-group-header` — full-width button, dark raised background, chevron rotates 90° when collapsed.
- `.set-group-row` — horizontal scroll container with snap and styled scrollbar.

---

### Phase 17 — Card view lightbox

**Motivation:** Clicking a collection card previously opened the edit modal directly, giving no way to just look at a card without accidentally editing it. Feature requested by @Awesmoe on GitHub.

**Lightbox overlay (`#card-view-overlay`):**
- Full-screen overlay (`position: fixed; inset: 0`) with a centred panel (`.card-view-panel`, max-width 900px).
- Desktop: side-by-side layout — artwork left (`.card-view-image-wrap`, up to 380px wide), info panel right.
- Mobile/tablet: portrait-stacked — artwork on top (280px / 180px resp.), info below with vertical scroll.
- Info panel shows: card name, set name + set code chip, card number, condition chip, quantity, price row (best price + variant), purchase info and P&L summary (full pricing mode only).
- "Edit entry" button at the bottom opens the edit modal.

**Tap/click flow change:**
- Collection poster cards now call `openCardView(entry)` (not `openEditModal`) on both click and keyboard enter.
- `.tapped` class management moved from `openEditModal` to `openCardView`.
- Edit from lightbox: `const entry = _cardViewEntry; closeCardView(); openEditModal(entry);` — entry captured into a local before `closeCardView()` nulls `_cardViewEntry`.

**Hover zoom removed:**
- `.poster-card:hover { transform: scale(1.04) }` and `.poster-card:hover img { transform: scale(1.06) }` removed. Both caused card art to be clipped by `overflow: hidden` at the card edges.

---

### Phase 18 — Mobile edit modal stabilisation

**Problem:** On mobile, opening the edit modal and then tapping an input field raised the soft keyboard. The modal used `max-height: 90dvh` (dynamic viewport height), which shrinks as the keyboard appears, causing the modal to visibly resize and the Save button to scroll off-screen or shift unpredictably.

**Root cause:** `dvh` tracks the *current* viewport height and changes in real time as the keyboard opens/closes. `svh` (small viewport height) is fixed at the minimum size the viewport can reach (i.e., with the keyboard open) and never changes during a keyboard event.

**CSS changes (`frontend/css/style.css`):**
- `.modal`: `max-height` changed from `90dvh` to `90svh` (with `dvh` as a fallback for browsers without `svh` support, placed first in the cascade so `svh` wins).
- `.modal`: `overflow-y: hidden` (scroll is now delegated to the body, not the modal container). `display: flex; flex-direction: column` so the body can grow and the actions stay at the bottom.
- `.modal-body`: added `flex: 1; overflow-y: auto; min-height: 0` — grows to fill available height and scrolls independently.
- `.form-actions`: added `position: sticky; bottom: 0; background: var(--bg-surface); padding-bottom: 0.75rem; z-index: 1` — Save button stays pinned at the bottom of the visible modal, always reachable.
- Mobile breakpoint `@media (max-width: 600px)`: updated from `max-height: 95dvh` to `max-height: 95dvh; max-height: 95svh`.

---

### Phase 19 — Per-card price tracking in collection-only mode

**Motivation:** Collection-only mode was all-or-nothing — either all cards were priced or none were. Users wanted to track prices for specific high-value cards (e.g. cards listed for trade) without enabling full pricing for the whole collection.

**New DB column (`backend/models.py`, migration `0005features`):**
- `track_price: Mapped[bool]` — opt-in price tracking per entry (default `false`).
- Also adds `for_trade` (Phase 21). Both use `server_default="false"` so existing rows are unaffected.

**Backend logic (`routers/collection.py`):**
- `add_to_collection`: fetches prices if `for_trade=True` OR `track_price=True` (collection_only) OR pricing is full. qty=0 entries never trigger a fetch regardless.
- `update_collection_entry`: if the patch toggles `track_price` from false→true or `for_trade` from false→true, a price fetch is triggered immediately for that entry.
- All write endpoints (`POST`, `PUT`, `DELETE`, `POST /bulk-missing`) require authentication if `AUTH_USERNAME` is set (Phase 22).

**Scheduler update (`backend/scheduler.py`):**
- In collection_only mode the nightly job now queries `WHERE (track_price = true OR for_trade = true) AND quantity > 0` instead of returning early unconditionally. If no tracked entries exist, it logs and returns.

**Frontend — `entryPricingOn(e)` helper (`collection.js`):**
- Returns `true` if `pricing_mode === 'full'`, or if `pricing_mode === 'collection_only'` and (`e.track_price` or `e.for_trade`). Used throughout `renderPosterCard`, `renderCollectionGrouped` value sums, and the card-view lightbox.

**Frontend — star toggle button:**
- New `poster-action-track` button (star icon) added to each poster card's action row. Calls `toggleTrackPrice(event, id, currentValue)`.
- In full pricing mode the button is hidden (all cards already priced).
- Active state: gold fill (`#F27E00`); inactive: muted outline.
- Edit modal and card-view lightbox both include a `track_price` checkbox row, shown only in collection_only mode.

---

### Phase 20 — Zero-quantity missing-card placeholders

**Motivation:** Users tracking set completion wanted to mark cards they're missing without leaving gaps in their roster. A qty=0 placeholder represents "I know this card exists but I don't own it."

**Backend changes:**
- `CollectionEntry.quantity` constraint relaxed to allow `0` (previously enforced `>= 1` at the Pydantic layer).
- `add_to_collection`: quantity `0` skips all price fetching.
- `list_collection`: qty=0 entries are included in the full collection response. Portfolio queries filter `quantity > 0` so missing cards do not distort value totals.
- New endpoint `POST /api/collection/bulk-missing`:
  - Accepts `{ set_id: int }`.
  - Fetches all cards for the set via `GET /sets/{set_id}/cards`.
  - Finds cards not yet in the user's collection (`card_api_id NOT IN` existing entries for this set).
  - Inserts qty=0, condition=`"NM"` placeholders for each missing card.
  - Returns `{ added: int }`.

**Frontend — missing card styling:**
- `renderPosterCard(e)` in `collection.js` applies `.poster-card--missing` to qty=0 entries: grayscale filter on the image, reduced opacity on the overlay.
- A `.poster-missing-badge` label ("Missing") overlays the bottom of the card.
- Missing cards excluded from `updateSidebarStats` card count but counted separately in a `sidebar-missing-row` stat (hidden when count is 0).
- "Show/Hide missing" toggle button (`btn-toggle-missing`) in collection page-actions. State stored in `localStorage`; when hidden, `.hidden` is toggled on each `.poster-card--missing` element.

**Frontend — "Track all missing" button in set detail:**
- `btn-bulk-missing` button in the set detail header, shown when a set is open, hidden when back on the grid.
- Calls `POST /api/collection/bulk-missing`; toasts "Added N missing cards as placeholders" or "All cards in this set are already tracked".
- Triggers `loadCollection()` on success so sidebar stats update.

**Add form change:** Quantity input `min` attribute changed from `1` to `0`. Helper text updated to explain that `0` = missing/wanted placeholder.

---

### Phase 21 — Trade Binder

**Motivation:** Users wanted to flag cards they're open to trading and share a quick view of them, complete with market prices for negotiation.

**New DB column:** `for_trade: Mapped[bool]` (same migration as Phase 19).

**Backend changes (`routers/collection.py`):**
- `GET /api/collection` gains `?for_trade=true` filter — returns only entries marked for trade.
- Trade entries always have pricing fetched/updated regardless of `pricing_mode` (trade cards must have prices for binder negotiation).

**New nav tab — Trade Binder:**
- Sidebar link, topbar link, and bottom-nav tab (4-item bottom nav; SVG icons shrunk from 22px → 20px to fit 320px width).
- `#view-trade-binder` section with summary bar (`trade-summary-bar`) and `#trade-binder-grid`.
- `loadTradeBinder()` and `renderTradeBinder()` in `frontend/js/trade-binder.js`.
- `renderTradePosterCard(e)`: always shows pricing; includes a remove-from-trade toggle button (active/blue state), edit button, and delete button.
- Summary bar: card count + total estimated value in EUR.

**Toggle button on collection cards:**
- `poster-action-trade` button (arrows icon) on each collection poster. Calls `toggleForTrade(event, id, currentValue)`.
- Active state: blue (`#3b82f6`); inactive: muted. Cards marked for trade show a `chip-trade` TRADE badge.
- Edit modal includes a `for_trade` checkbox. Card-view lightbox includes both trade and track-price toggles.

**Touch UX:** Tap-to-reveal handler added to `tradeBinderGrid` in `trade-binder.js` (same pattern as `collectionGrid` and `setCardsGrid`).

---

### Phase 22 — Optional JWT authentication

**Motivation:** The app was originally intended for a private network (Tailscale) with no auth. To support broader deployment, authentication was added as an opt-in layer: if `AUTH_USERNAME` is not set in the environment the app behaves exactly as before with no visible auth UI. Existing single-user deployments are completely unaffected.

**Backend — `backend/services/auth.py`:**
- `require_auth(request)` async dependency: returns `None` (not raises) when `AUTH_USERNAME` env is not set. When set, validates the `Authorization: Bearer <token>` header; raises HTTP 401 if missing or invalid.
- `create_token(username)` / `decode_token(token)` using `python-jose[cryptography]` with `JWT_SECRET_KEY` env var.
- Password verification with `passlib[bcrypt]`.
- New dependencies in `requirements.txt`: `python-jose[cryptography]==3.3.0`, `passlib[bcrypt]==1.7.4`.

**Backend — `backend/routers/auth.py`:**
- `POST /api/auth/login` — accepts `{username, password}`, returns `{token}` on success or HTTP 401.
- `GET /api/auth/status` — returns `{auth_enabled: bool, authenticated: bool}`.
- `GET /api/auth/logout` — informational (JWT is stateless; actual logout is client-side token deletion).

**Protected endpoints:** All write operations (`POST /collection`, `PUT /collection/{id}`, `DELETE /collection/{id}`, `POST /collection/bulk-missing`, `PUT /settings/{key}`, `POST /prices/refresh`) use `Depends(require_auth)`. Read operations always public.

**Frontend — login modal (`#login-modal-overlay`):**
- Username + password form; error display; shown automatically when a write action requires auth.
- `requireAuth()` async helper in `app.js`: if a token is stored and valid → resolves immediately. Otherwise shows the login modal and queues a Promise resolver. Multiple simultaneous calls (e.g. user double-taps add) all share the same queue and resolve after one login.
- `apiFetch()` updated: adds `Authorization: Bearer <token>` header when a token exists; on HTTP 401, clears the stored token, calls `requireAuth()`, and retries the original request once (prevents infinite loops with a `_retried` flag).

**Frontend — auth UI in sidebar:**
- Logged-out state: "Sign in" button.
- Logged-in state: username display + "Sign out" button.
- `loadAuthState()` calls `GET /api/auth/status` on page load; `updateAuthUI()` toggles the sidebar state.
- Settings gear button also gated through `requireAuth()`.

**Env vars added (`.env.example`):**
```
AUTH_USERNAME=admin          # leave unset to disable auth
AUTH_PASSWORD=yourpassword   # bcrypt hash also accepted
JWT_SECRET_KEY=changeme      # any random string; rotate to invalidate all sessions
```

**`docker-compose.yml` update:** The backend's `environment:` block explicitly names every variable forwarded into the container — variables in `.env` that aren't listed are silently dropped. Added `AUTH_USERNAME`, `AUTH_PASSWORD`, and `JWT_SECRET_KEY` with empty-string fallbacks:
```yaml
AUTH_USERNAME: ${AUTH_USERNAME:-}
AUTH_PASSWORD: ${AUTH_PASSWORD:-}
JWT_SECRET_KEY: ${JWT_SECRET_KEY:-}
```
Without this, `GET /api/auth/status` returns `auth_enabled: false` even when the values are set in `.env`.

---

### Phase 23 — Settings gear accessible on mobile portrait

**Problem:** On phones (≤600px), the topbar was hidden entirely in favour of the bottom nav. The settings gear button lived inside the topbar, so it was completely inaccessible in portrait mode — users had no way to open the Settings modal without rotating to landscape.

**Fix:**
- The topbar remains hidden on portrait mobile (restoring the original Phase 12 behaviour).
- A new `<button class="btn-settings-mobile">` element is added to `index.html`, positioned `fixed` at `top: 0.75rem; right: 0.75rem` via `z-index: 110`. It is `display: none` at all wider breakpoints (tablet/desktop already have the topbar gear and sidebar gear).
- Only visible at `@media (max-width: 600px)`.
- Wired to the same `openSettingsModal()` / `requireAuth()` handler as the other two gear buttons in `app.js`.

**Result:** A small gear button floats in the top-right corner on portrait mobile, leaving the existing layout completely undisturbed. No layout shifts; no regressions on tablet or desktop.

**CSS/JS cache-buster:** bumped from `?v=24` to `?v=25`.

---

### Phase 24 — Full set card grid with ownership styling and auto-backfill

**Motivation:** The set detail view only showed cards that had already been cached in the local DB (i.e., cards the user had previously looked up or added to their collection). Opening a set with 335 cards but only 5 cached would show only those 5. Users wanted to see the *entire* set — owned cards in full colour, everything else greyed out.

**Backend — `GET /api/sets/{set_id}/cards` (`routers/sets.py`):**
- Previously fetched from the PokéWallet API only when `len(cached_cards) == 0`. Now fetches whenever `len(cached_cards) < set.card_count` — i.e. the cache is incomplete regardless of how many cards are already there.
- After cards are loaded, runs a second query against the `collection` table summing `quantity` (where `quantity > 0`) per card. Returns each card as a dict extending `CardOut` with an `owned_quantity` field. Zero-quantity "missing placeholder" entries do not count as owned.
- `response_model` removed from the decorator so the extra field passes through.

**Frontend — `renderSetCards()` (`frontend/js/sets.js`):**
- Each card checks `c.owned_quantity > 0`. Unowned cards get the `poster-card--missing` class (greyscale filter + reduced opacity — the same CSS already used in the collection view).
- Owned cards get a `poster-qty-badge` showing the quantity (reuses the existing badge style).
- `openSetDetail()` is called again after "Track all missing" succeeds, so newly added placeholders immediately appear greyed out without a manual reload.

**Frontend — auto-refresh after adding a card (`frontend/js/search.js`):**
- After the add-card form submits successfully, if `_currentSet` is set (set detail is open), calls `openSetDetail(_currentSet)` to re-fetch the set cards. The newly owned card flips from grey to full colour instantly.

**Scheduler — `backfill_incomplete_sets()` (`backend/scheduler.py`):**
- New hourly job (runs at :05 every hour, 5 min after the counter resets at :00).
- Finds all sets in the user's collection where the DB card count is still less than `set.card_count`.
- For each incomplete set, calls `pokewallet.get_set_cards()` and inserts missing `Card` rows. The `if not existing:` guard makes it idempotent.
- Checks `pokewallet.is_hourly_limit_reached()` before each set. If the limit is hit mid-run it logs a warning and exits; the job resumes automatically next hour.
- Only processes sets that appear in the user's collection — never tries to pre-fetch all 700+ sets.

**Cache-buster:** `?v=25` → `?v=26`.

---

### Phase 25 — Graceful 429 handling for PokéWallet API

**Problem:** The internal hourly counter (`_calls_this_hour`) resets on every container restart. After a restart, `is_hourly_limit_reached()` returns `False` even if PokéWallet's real server limit was already exhausted. Any API call would receive a `429 Too Many Requests`, `resp.raise_for_status()` would throw an unhandled `httpx.HTTPStatusError`, and FastAPI surfaced it as a 500. Affected users saw a toast error and no cards in set detail.

**Fix — `backend/services/pokewallet.py`:**
- All four API functions (`search_cards`, `get_card`, `get_sets`, `get_set_cards`) now check `resp.status_code == 429` before calling `raise_for_status()` and return `[]` / `None` instead of raising — the same defensive pattern already used for 404.

**Fix — `backend/routers/sets.py` `get_set_cards`:**
- The API fetch block now only inserts cards when `raw_cards` is non-empty (previously it committed an empty loop then re-queried, which was harmless but fragile).
- Always re-queries the DB after the fetch attempt. If the API was rate-limited and returned `[]`, the endpoint falls back to serving whatever is already cached in the DB instead of returning an empty list.
- Result: opening a set while rate-limited shows the cards that are already cached rather than erroring.

---

### Phase 26 — Opt-in auto-load full sets

**Motivation:** The Phase 24 auto-fetch behaviour (always try to fill incomplete sets on open) could silently exhaust the PokéWallet API quota whenever a user browsed sets, especially after a container restart (which resets the in-memory rate counter). Made it opt-in so users understand the trade-off before enabling it.

**New setting: `auto_fetch_full_set`** (values: `"enabled"` / `"disabled"`, default `"disabled"`):
- `backend/routers/settings.py`: added to `_VALID_VALUES`; new `get_auto_fetch_setting(session)` helper (mirrors `get_pricing_mode`).
- `backend/routers/sets.py` `get_set_cards`: only attempts the PokéWallet API fetch when `auto_fetch_full_set == "enabled"` AND cache is incomplete. When disabled (or rate-limited), always falls back to serving whatever is already in the DB.
- `backend/scheduler.py` `backfill_incomplete_sets`: exits early when the setting is disabled.

**Settings modal:**
- New "Auto-load full sets" toggle row (Off / On) added after the Grouped view layout row.
- When switched to On: a warning banner appears explaining that each set browsed uses 1 API call, quota can be exhausted quickly, and the hourly backfill job fills gaps automatically over time.
- `updateAutoFetchUI(value)` function mirrors the existing `updateSettingsModeUI` pattern.
- `window.appSettings` default includes `auto_fetch_full_set: 'disabled'`.

**Cache-buster:** `?v=26` → `?v=27`.

---

### Phase 27 — Server-side image disk cache, lazy loading, and set-images toggle

**Motivation:** Opening a 335-card set for the first time fired 335 separate image API calls (one per card), which exhausted the PokéWallet free-tier quota (100/hour) instantly. Three complementary fixes were implemented.

**Option 1 — Lazy loading (`frontend/js/sets.js`):**
- `renderSetCards()` now renders `<img data-src="...">` instead of `<img src="...">`.
- An `IntersectionObserver` (rootMargin: 150px) swaps `data-src → src` as each card scrolls into view. Only images the user actually sees get loaded.
- The observer is disconnected on back-navigation and on each `renderSetCards()` call to avoid memory leaks. Module-level `_imageObserver` tracks the current observer.

**Option 2 — Server-side image disk cache (`backend/routers/images.py`, `docker-compose.yml`):**
- `images.py` checks `./image_cache/{card_api_id}` before hitting any upstream. On a cache miss, fetches from PokéWallet or PriceCharting CDN, writes `{id}` (raw bytes) and `{id}.ct` (content-type string sidecar), then serves the response.
- Cached responses use `Cache-Control: public, max-age=604800` (7 days). Each image costs exactly one API call ever, across all browser sessions and container restarts.
- `docker-compose.yml`: bind mount `./image_cache:/app/image_cache` so the cache lives on the host filesystem.
- `IMAGE_CACHE_DIR` env var overrides the path (defaults to `/app/image_cache`).
- `.gitignore`: `image_cache/` excluded.
- **Backup:** `tar -czf image_cache_backup.tar.gz image_cache/`

**Option 3 — Set-images toggle (`backend/routers/settings.py`, settings modal):**
- New setting: `set_images` (`"visible"` / `"hidden"`, default `"visible"`).
- When `"hidden"`, `renderSetCards()` renders `cardPlaceholder()` tiles instead of `<img>` tags — zero image API calls. Cards are still identifiable via name, number, and rarity in the poster overlay.
- Settings modal: new "Set card images" Visible / Hidden toggle row (no warning banner needed — no quota implication for hiding).

**Cache-buster:** `?v=27` → `?v=28`.

---

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

### Phase 28 — First-boot onboarding wizard

**Motivation:** New users had no guided setup flow. The API key had to be configured in `.env` with no in-app feedback, and pricing/layout preferences were buried in the Settings modal. The wizard ensures new deployments are correctly configured before the app loads any data.

**Migration `0006_add_onboarding_settings.py`:**
- Seeds `pokewallet_api_key_status = 'unknown'` for all deployments.
- Seeds `onboarding_complete` conditionally: `'true'` if `SELECT COUNT(*) FROM collection > 0` (existing deployment skips the wizard), `'false'` otherwise (fresh install shows it). Both use `ON CONFLICT DO NOTHING` so the migration is safe to replay.

**Backend — `routers/settings.py`:**
- `_VALID_VALUES` extended with `onboarding_complete` (`true`/`false`) and `pokewallet_api_key_status` (`valid`/`invalid`/`unknown`).
- `_upsert_setting(session, key, value)` — shared helper used by both new endpoints.
- `POST /api/settings/validate-api-key` — makes a live `GET https://api.pokewallet.io/sets?limit=1` with the `POKEWALLET_API_KEY` env var. Returns `{"status":"valid"}` on HTTP 200 + `success:true`, or `{"status":"invalid","detail":"..."}` on auth errors, network failures, or unexpected responses. Upserts `pokewallet_api_key_status` either way.
- `POST /api/settings/complete-onboarding` — accepts `{pricing_mode, grouped_layout}`. Validates both fields, upserts `pricing_mode` and `onboarding_complete = "true"`, returns `{success: true, grouped_layout}`. `grouped_layout` is frontend-only (stored in `localStorage`), so it is echoed back rather than persisted.

**Frontend — `frontend/js/onboarding.js`** (new file):
- `initOnboarding()` — removes `.hidden` from `#onboarding-overlay`, wires up all button listeners.
- `_showOnboardingStep(n)` — toggles `.active` on `.onboarding-step[data-step]` and `.step-dot[data-step]` elements.
- `_validateApiKey()` — calls `POST /api/settings/validate-api-key`; shows spinner during request; on success shows green checkmark and unhides the Next button; on failure shows the error message and re-enables the Retry button. The user cannot advance past step 1 without a valid key.
- `_completeOnboarding()` — calls `POST /api/settings/complete-onboarding`; stores `grouped_layout` in `localStorage`; patches `window.appSettings`; hides the overlay; calls `applySettingsToUI()` + `routeFromHash()` to boot the normal app.

**Frontend — `app.js` integration:**
- `DOMContentLoaded` handler now checks `window.appSettings.onboarding_complete === 'false'` after `loadSettings()`. If true: calls `initOnboarding()` and `return`s early — `routeFromHash()`, sidebar stats, and all collection API calls are skipped until onboarding completes.

**Frontend — `index.html`:**
- `#onboarding-overlay` added as a direct child of `<body>` (outside `.app-layout`), before the modals. It covers everything with `position:fixed; inset:0; z-index:10000; background:var(--bg)` — solid full-screen takeover, not a backdrop.
- 4 steps: Welcome → API Key validation → Preferences (pricing mode + grouped layout) → Summary + "Start Collecting".
- Preference toggles reuse the existing `.mode-toggle`/`.mode-btn` pill component.
- Step indicator uses animated pill dots (`.step-dot`): inactive dots are 8px circles, active dot expands to 24×8px pill.

**CSS/JS cache-buster:** `?v=29` → `?v=30`.

**Follow-up fix (same feature):**
- Step 2 toggles made full-width via `.mode-toggle.onboarding-toggle` modifier (sets `width:100%` on the container and `flex:1; min-height:44px` on each button — doesn't affect the settings modal).
- Added **Auto-load Full Sets** (Off/On, default Off) and **Set Card Images** (Visible/Hidden, default Visible) preference blocks to step 2.
- A warning banner (`#onboarding-api-warning`, reuses `.settings-warning`) appears when both Auto-load and Card Images are enabled simultaneously, explaining the free-plan quota risk.
- Step 3 summary expanded from 2 rows to 4 (adds Auto-load Sets and Set Card Images).
- `POST /api/settings/complete-onboarding` now accepts and saves `auto_fetch_full_set` and `set_images` (both optional with safe defaults so older clients still work).
- Cache-buster bumped to `?v=31`.

---

### Phase 29 — PokéWallet API usage display

**Motivation:** Quota exhaustion was invisible — users had no way to tell how many calls had been made without reading logs. Added passive usage display in two places.

**Backend — `GET /api/rates`** (`main.py`):
- Returns `{ calls_this_hour, calls_today, hourly_limit (80), daily_limit (1000), daily_warn (800) }`.
- Reads from the existing in-memory counters in `pokewallet.py` via a new `get_calls_this_hour()` getter (mirrors the existing `get_calls_today()`).
- Counters reset on container restart; this is documented/expected behaviour.

**Frontend — sidebar stat row (`#sidebar-api-row`):**
- Always visible on desktop. Shows `N / 80h · Nd` (hourly count / hourly limit · daily count).
- Colour coding on the hourly figure: normal (muted) → orange/accent at ≥50% → red at ≥80%.

**Frontend — settings modal (`#settings-api-usage-section`):**
- Two 4px progress bars at the bottom of the modal: "This hour" (against hourly limit of 80) and "Today" (against daily limit of 1000).
- Bar fill transitions orange at ≥50%, red at ≥80%.
- Refreshed every time the modal opens, plus on page load and every 60 seconds via `setInterval`.

**CSS:** `.api-usage-bar` / `.api-usage-fill` (with `.warn` and `.critical` modifier classes) + `.sidebar-stat-value.api-warn` / `.api-critical` colour overrides.

**Cache-buster:** `?v=32` → `?v=33`.

---

### Phase 30 — Set group reordering in grouped view

**Motivation:** In grouped view, sets were always sorted alphabetically by set name. Users wanted to be able to pin favourite sets to the top or arrange them in a custom order.

**Reorder mode toggle (`#btn-reorder-sets`):**
- New icon-only button in the collection page-actions bar.
- Hidden when in flat view; shown (and highlighted orange when active) when grouped view is active.
- Toggling off grouped view also exits reorder mode.

**Drag-and-drop (desktop, `@media (hover: hover)`):**
- When reorder mode is on, each `.set-group` gets `draggable="true"` and a two-line grip handle (`set-group-drag-handle`) appears flush to the left of the header, styled as a visual extension of the header pill.
- `dragstart` records the dragged element; `dragover` live-inserts it before/after the target (top/bottom half detection via `getBoundingClientRect`); `dragend` calls `saveSetGroupOrder()` which reads the final DOM order and persists to `localStorage`.
- Dragging group fades to 40% opacity; a 2px orange `box-shadow` line indicates the drop target.

**Up/Down buttons (touch, `@media (hover: none)`):**
- On touch devices the drag handle is hidden and replaced by stacked ↑/↓ arrow buttons (`set-group-move-btn`) on the right edge of each header.
- `moveSetGroup(setId, direction)` swaps the entry in the saved order array and re-renders from the cached `_lastEntries` (no API call).
- First group has ↑ disabled; last group has ↓ disabled.

**Persistent order (`localStorage` key `setGroupOrder`):**
- Stored as a JSON array of set IDs in the user's preferred order.
- `renderCollectionGrouped` reads `setGroupOrder` and sorts groups accordingly. Sets not present in the saved array (newly added sets) fall back to alphabetical and appear after the ordered groups.

**Re-render without API call:**
- `loadCollection()` caches the fetched entries in `_lastEntries`.
- `setReorderMode()` and `moveSetGroup()` call `renderCollection(_lastEntries)` — instant re-render from cache with no server roundtrip.

**HTML structure change:**
- `.set-group-header` (`<button>`) is now wrapped in a `.set-group-header-row` flex div (alongside the drag handle and move buttons). All existing JS and CSS selectors continue to work: `btn.closest('.set-group')` traverses the extra wrapper transparently, and `.set-group.collapsed .set-group-body` still matches.

**CSS/JS cache-buster:** `?v=33` → `?v=34`.

**Follow-up fixes (same feature):**
- **Collapse not working:** the original implementation set `localStorage` keys to `'collapsed'` and relied on `renderCollection` reading them back, but this chain was silently unreliable. Fixed by applying collapse/restore directly to the DOM *after* the re-render — synchronous DOM manipulation is always reliable.
- **Auth gate:** the reorder button click handler now calls `requireAuth()` before activating reorder mode. When auth is disabled (`AUTH_USERNAME` unset), `requireAuth()` resolves immediately — no behaviour change for unauthenticated deployments.
- **State cleanup:** `_savedCollapseStates` is now cleared when leaving grouped view to avoid stale state leaking into subsequent renders.
- **Cache-buster:** `?v=34` → `?v=35`.

---

### Phase 31 — Set group row wrapping

**Problem:** With large sets, cards in the grouped view's horizontal layout overflowed the viewport, requiring horizontal scrolling. Most noticeable at 1440p and worse at lower resolutions.

**Fix:** Removed `overflow-x: auto`, `scroll-snap-type`, `-webkit-overflow-scrolling`, and the custom scrollbar styles from `.set-group-row`. Replaced with `flex-wrap: wrap` so cards flow onto new lines when they reach the container edge. The `.set-group-row .poster-card` rule retains `flex-shrink: 0; width: 148px` so card sizes are unchanged.

**Cache-buster:** `?v=35` → `?v=36`.

---

### Phase 32 — Sort cards within set groups

**Motivation:** Cards within each set group appeared in arbitrary insertion order. Users wanted to sort by set number or rarity.

**Sort dropdown (`#collection-sort`):**
- `<select>` element in the collection page-actions bar, styled to match `.btn-secondary` (`.sort-select` CSS class, `appearance: none` with a custom SVG chevron arrow).
- Hidden in flat view; shown in grouped view (toggled by `setCollectionViewMode`, same pattern as the reorder button).
- Four options: **№ Asc** (default), **№ Desc**, **Rarity ↑** (Common first), **Rarity ↓** (Hyper Rare first).
- Selection persists in `localStorage` under `collectionGroupSort`.

**Sort logic (`collection.js`):**
- `cardNumberSortKey(num)` — extracts the first integer from any card number format (`116/159` → 116, `SWSH050` → 50, `JTG 116` → 116, `167` → 167). Cards without a number sort last (key 99999).
- `RARITY_ORDER` — 19-entry map assigning a numeric tier to each rarity string found in the DB (Common=1 … Hyper Rare=14, Promo=18, Code Card=19).
- `sortGroupEntries(entries)` — returns a sorted copy of the entries array for the active sort mode. Rarity sorts use card number as a tiebreaker within the same rarity tier.
- Applied in `renderCollectionGrouped` by replacing `group.entries.map(...)` with `sortGroupEntries(group.entries).map(...)`. Sorting happens at render time from `_lastEntries` — no API call on sort change.

**Cache-buster:** `?v=36` → `?v=37`.

---

### Phase 33 — Sort in flat view + rarity indicator on cards

**Motivation:** The sort dropdown was only visible in grouped view. Users wanted to sort by rarity in flat view too (set number sorting doesn't make sense outside a group context). Also, card rarity wasn't visible at a glance in the poster grid.

**Flat-view sort:**
- `updateSortSelectOptions(mode)` replaces the old hidden-toggle logic in `setCollectionViewMode`. In flat mode it hides and disables the two `option[value^="number_"]` entries and falls back to `rarity_desc` if the current selection was a number sort. In grouped mode it re-enables them.
- `renderCollectionFlat` now calls `sortGroupEntries(entries)` before mapping, so rarity sort applies across the whole flat list.
- The sort select is now always visible (in both flat and grouped modes); only the number options are conditionally disabled.

**Rarity indicator on poster cards:**
- `.poster-rarity` CSS class: `font-size: 0.58rem`, `color: rgba(255,255,255,0.42)`, `overflow: hidden`, `text-overflow: ellipsis`, `white-space: nowrap`. Placed between `.poster-name` and `.poster-meta` in the overlay.
- `renderPosterCard` conditionally appends `<div class="poster-rarity">${e.card.rarity}</div>` when `e.card.rarity` is set.
- Cards with no rarity (some promos) simply omit the element.
- Initial styling was faint grey text (replaced in Phase 34).

**Cache-buster:** `?v=37` → `?v=38`.

---

### Phase 34 — Sort select always visible fix + rarity chip badge

**Motivation:** After Phase 33, the sort dropdown was still invisible in all modes because the `hidden` class was never removed from the element. Separately, the faint rarity text was hard to read sandwiched between the bold card name and the set/number metadata.

**Sort select visibility fix:**
- The `<select id="collection-sort">` in `index.html` had `class="sort-select hidden"`. `updateSortSelectOptions(mode)` only ever toggled the number options inside it — it never removed `hidden` from the select itself. Fix: removed the `hidden` class from the HTML entirely. The select is now always visible; `updateSortSelectOptions` continues to disable/hide number-sort options in flat mode.

**Rarity chip badge:**
- `.poster-rarity` restyled as a frosted-glass pill matching the condition chip aesthetic: `display: inline-block`, `padding: 0.1rem 0.42rem`, `border-radius: 100px`, `font-weight: 600`, `color: rgba(255,255,255,0.9)`, `background: rgba(255,255,255,0.15)`, `border: 1px solid rgba(255,255,255,0.25)`. No JS changes required.

**Cache-buster:** `?v=39` → `?v=40` (sort fix) → `?v=41` (rarity chip).

---

### Phase 35 — Sets page fixes for PriceCharting promo set

**Motivation:** The `pc_promo` set (cards added via PriceCharting URL) appeared as a blank icon on the sets page with no name, owned count, or overlay visible.

**Root cause 1 — onerror wiped card content:**
- The set poster `<img>` `onerror` handler did `this.parentElement.innerHTML = setPlaceholder(...)`, replacing the entire card HTML (name, badges, overlay) with just the placeholder icon. PokéWallet sets are unaffected because their images load. `pc_promo` always 404s on the PokéWallet image endpoint, so the whole card was wiped.
- Fix: changed to `this.style.display='none'; this.parentElement.insertAdjacentHTML('afterbegin', setPlaceholder(...))` — matches the collection card pattern: hide the broken img, insert the placeholder alongside the existing content.

**Root cause 2 — no image for pc_promo:**
- Even with the onerror fix, the set showed a placeholder icon. The user identified a suitable image at `https://www.pricecharting.com/images/pokemon-sets/pokemon-promo.png`.
- Fix: in `renderSetsGrid` (`sets.js`), `imageUrl` is set to the PriceCharting URL when `s.set_id === 'pc_promo'`; all other sets use the PokéWallet proxy as before. `<img>` tags are not subject to CORS so the external URL loads without issue.

**Cache-buster:** `?v=41` → `?v=42` (onerror fix) → `?v=43` (promo image).

### Phase 36 — Optimistic DOM removal for Trade Binder actions

**Motivation:** Removing a card from the Trade Binder (via the trade-icon button or the delete button) required a full page refresh before the card disappeared. This was because `toggleForTrade` and `deleteEntry` both called `loadCollection()` after the API call, which re-renders the collection view but never touches `#trade-binder-grid`.

**Fix:** Added `removeCardFromDOM(event)` in `collection.js` that uses `event.target.closest('[data-entry]')` to find the card element and remove it instantly before the API call is awaited. Both `toggleForTrade` (when `currentValue` is true) and `deleteEntry` call it immediately, so the card disappears on click. The subtitle count and empty-state visibility are updated at the same time.

Both call sites for `deleteEntry` (`renderPosterCard` in `collection.js` and `renderTradePosterCard` in `trade-binder.js`) were updated to pass `event` as the first argument.

**Cache-buster:** `?v=43` → `?v=44`.

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
- **Authentication is opt-in** — set `AUTH_USERNAME` + `AUTH_PASSWORD` + `JWT_SECRET_KEY` in `.env` to enable. When unset (default), all endpoints are public — intended for a private server behind Tailscale or similar. Do not expose port 3003/8014 to the public internet without TLS and authentication.
- **PriceCharting scraping reliability** — PriceCharting currently serves clean HTML with no Cloudflare interference, but this could change. If scraping starts failing, check logs for `ScrapeError` / `ScrapeParseError`. The last cached price is retained on failure; the Stale badge will appear in the UI after the TTL lapses.
- **PriceCharting prices are USD** — converted to EUR at fetch time using the ECB rate cached for 24 hours. If `api.frankfurter.app` is unreachable the fallback rate `0.92` is used.
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
| `backend/models.py` | All SQLAlchemy ORM models (including `AppSetting`) |
| `backend/services/pokewallet.py` | All PokéWallet API calls + normalisation |
| `backend/services/price_cache.py` | Cache TTL logic, `get_price()`, `scrape_and_store()` |
| `backend/services/pricecharting_scraper.py` | PriceCharting HTML scraper (curl_cffi + selectolax) |
| `backend/services/currency.py` | USD→EUR conversion via Frankfurter/ECB API |
| `backend/routers/collection.py` | Collection CRUD; enriches entries with set_name/set_card_count |
| `backend/routers/prices.py` | Price fetch and refresh endpoints (gated on pricing_mode) |
| `backend/routers/portfolio.py` | Portfolio value aggregation |
| `backend/routers/images.py` | Card artwork proxy (PokéWallet or Google Storage CDN) |
| `backend/routers/manual_cards.py` | `POST /api/cards/manual` — scrape by PriceCharting URL |
| `backend/routers/settings.py` | App settings CRUD + `get_pricing_mode()` helper |
| `backend/scheduler.py` | APScheduler job definitions; nightly refresh + hourly set backfill |
| `frontend/js/app.js` | Routing, fetch helpers, toast, settings modal, `loadSettings()` |
| `frontend/js/collection.js` | Poster grid, grouped view, collapsible sections, view toggle |
| `frontend/js/search.js` | Search modal + add form |
| `frontend/js/portfolio.js` | Portfolio view + Chart.js; disabled state in collection-only mode |
| `frontend/js/sets.js` | Sets browser + set detail + "Track all missing" button |
| `frontend/js/trade-binder.js` | Trade Binder view — filtered collection of `for_trade` cards |
| `backend/routers/auth.py` | JWT auth endpoints (`/api/auth/login`, `/status`, `/logout`) |
| `backend/services/auth.py` | `require_auth()` dependency + JWT helpers |

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
| `AUTH_USERNAME` | Login username — leave unset to disable auth entirely | — |
| `AUTH_PASSWORD` | Login password (plaintext or bcrypt hash) | — |
| `JWT_SECRET_KEY` | JWT signing secret — rotate to invalidate all sessions | — |

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
