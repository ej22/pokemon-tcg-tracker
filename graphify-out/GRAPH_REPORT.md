# Graph Report - .  (2026-04-20)

## Corpus Check
- 44 files · ~152,604 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 405 nodes · 733 edges · 32 communities detected
- Extraction: 66% EXTRACTED · 34% INFERRED · 0% AMBIGUOUS · INFERRED: 251 edges (avg confidence: 0.64)
- Token cost: 18,500 input · 4,800 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Backend Data & Routers|Backend Data & Routers]]
- [[_COMMUNITY_Frontend App Core|Frontend App Core]]
- [[_COMMUNITY_UI Design & UX Phases|UI Design & UX Phases]]
- [[_COMMUNITY_Backend Services & Scheduler|Backend Services & Scheduler]]
- [[_COMMUNITY_Architecture Docs & Config|Architecture Docs & Config]]
- [[_COMMUNITY_Manual Cards & PriceCharting|Manual Cards & PriceCharting]]
- [[_COMMUNITY_Feature Evolution Phases|Feature Evolution Phases]]
- [[_COMMUNITY_Frontend Settings & Utilities|Frontend Settings & Utilities]]
- [[_COMMUNITY_JWT Authentication|JWT Authentication]]
- [[_COMMUNITY_App Settings & Config|App Settings & Config]]
- [[_COMMUNITY_Image Cache Service|Image Cache Service]]
- [[_COMMUNITY_Onboarding Wizard|Onboarding Wizard]]
- [[_COMMUNITY_Currency Exchange Service|Currency Exchange Service]]
- [[_COMMUNITY_Alembic Migration Engine|Alembic Migration Engine]]
- [[_COMMUNITY_Sets API Router|Sets API Router]]
- [[_COMMUNITY_Track Price Migration|Track Price Migration]]
- [[_COMMUNITY_Initial Schema Migration|Initial Schema Migration]]
- [[_COMMUNITY_URL Rename Migration|URL Rename Migration]]
- [[_COMMUNITY_Onboarding Settings Migration|Onboarding Settings Migration]]
- [[_COMMUNITY_App Settings Migration|App Settings Migration]]
- [[_COMMUNITY_Image URL Migration|Image URL Migration]]
- [[_COMMUNITY_Manual Cards Migration|Manual Cards Migration]]
- [[_COMMUNITY_Rate Limiting & API Guard|Rate Limiting & API Guard]]
- [[_COMMUNITY_Image Disk Cache Docs|Image Disk Cache Docs]]
- [[_COMMUNITY_Auth Header Pattern|Auth Header Pattern]]
- [[_COMMUNITY_Routers Init|Routers Init]]
- [[_COMMUNITY_Services Init|Services Init]]
- [[_COMMUNITY_Docker Workflow|Docker Workflow]]
- [[_COMMUNITY_pgAdmin Service|pgAdmin Service]]
- [[_COMMUNITY_Project Scaffold|Project Scaffold]]
- [[_COMMUNITY_Sets View Phase|Sets View Phase]]
- [[_COMMUNITY_Full Set Grid Phase|Full Set Grid Phase]]

## God Nodes (most connected - your core abstractions)
1. `Card` - 34 edges
2. `Set` - 26 edges
3. `index.html — Single-Page Application Shell` - 23 edges
4. `apiFetch()` - 20 edges
5. `CollectionEntry` - 17 edges
6. `get_price()` - 17 edges
7. `ScrapeError` - 17 edges
8. `PriceCache` - 15 edges
9. `scrape_and_store()` - 13 edges
10. `toast()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `_updateOnboardingSummary()` --calls--> `Set`  [INFERRED]
  frontend/js/onboarding.js → backend/models.py
- `PokéTCG Tracker — Collection View Screenshot` --references--> `PokéTCG Tracker — Self-Hosted Collection App`  [EXTRACTED]
  frontend.png → README.md
- `PokéTCG Tracker — Collection View Screenshot` --references--> `Sidebar Navigation (desktop)`  [INFERRED]
  frontend.png → frontend/index.html
- `PokéTCG Tracker — Collection View Screenshot` --references--> `Collection View Section`  [INFERRED]
  frontend.png → frontend/index.html
- `renderCollectionGrouped()` --calls--> `Set`  [INFERRED]
  frontend/js/collection.js → backend/models.py

## Hyperedges (group relationships)
- **Price Pipeline: get_price → cache check → PokéWallet/PriceCharting → price_history + price_cache** — claude_md_get_price, claude_md_price_cache_service, claude_md_pokewallet_service, technical_md_pricecharting_fallback, handover_arch_decision_two_price_tables [EXTRACTED 0.95]
- **Three-Tier Responsive Navigation: Sidebar (desktop) + Topbar (tablet) + Bottom Nav (mobile)** — index_html_sidebar_nav, index_html_topbar_nav, index_html_bottom_nav, index_html_btn_settings_mobile [EXTRACTED 0.92]
- **Pricing Mode Gate: settings toggle → backend guard → scheduler → frontend conditional render** — readme_pricing_modes, handover_phase15_pricing_mode_toggle, technical_md_price_fetch_logic, index_html_pricing_mode_toggle, technical_md_app_settings_table [EXTRACTED 0.90]

## Communities

### Community 0 - "Backend Data & Routers"
Cohesion: 0.08
Nodes (61): Base, BaseModel, add_to_collection(), bulk_missing(), BulkMissingRequest, _enrich_entry(), list_collection(), Add zero-quantity placeholder entries for every card in a set not yet in the col (+53 more)

### Community 1 - "Frontend App Core"
Cohesion: 0.08
Nodes (45): apiFetch(), requireAuth(), routeFromHash(), toast(), updateSidebarStats(), applyMissingFilter(), bestPrice(), closeCardView() (+37 more)

### Community 2 - "UI Design & UX Phases"
Cohesion: 0.08
Nodes (33): PokéTCG Tracker — Collection View Screenshot, Architecture Decision: Vanilla JS (no framework), Phase 12 — Mobile Responsive Layout, Phase 17 — Card View Lightbox, Phase 28 — First-Boot Onboarding Wizard, Phase 29 — PokéWallet API Usage Display, Phase 32 — Sort Cards Within Set Groups, Add Card Modal (search + URL + form steps) (+25 more)

### Community 3 - "Backend Services & Scheduler"
Cohesion: 0.11
Nodes (26): api_rates(), lifespan(), Return current in-memory PokéWallet API call counters., extract_cardmarket_prices(), get_calls_this_hour(), get_calls_today(), get_card(), _get_headers() (+18 more)

### Community 4 - "Architecture Docs & Config"
Cohesion: 0.07
Nodes (29): Alembic Database Migrations, APScheduler AsyncIOScheduler, Caddy Frontend Reverse Proxy, FastAPI Backend Service, get_price() — Single Price Entry Point, _normalise_card() — Card Data Flattener, Placeholder Sets Auto-Insert Pattern, pokewallet.py — PokéWallet API Service (+21 more)

### Community 5 - "Manual Cards & PriceCharting"
Cohesion: 0.11
Nodes (26): add_manual_card(), ManualCardRequest, Endpoint for adding a card by PriceCharting product URL.  Used for promo cards a, Scrape a PriceCharting product page and return card metadata + prices.      Resp, build_api_id(), canonicalize_url(), _extract_set_slug(), fetch_html() (+18 more)

### Community 6 - "Feature Evolution Phases"
Cohesion: 0.08
Nodes (26): Phase 10 — Netflix-Style Poster Grid + Image Proxy, Phase 14 — PriceCharting Scraper for Promo Cards, Phase 16 — Collection Grouped by Set, Phase 20 — Zero-Quantity Missing Card Placeholders, Phase 21 — Trade Binder, Phase 22 — Optional JWT Authentication, Phase 30 — Set Group Reordering in Grouped View, Phase 33 — Sort in Flat View + Rarity Indicator (+18 more)

### Community 7 - "Frontend Settings & Utilities"
Cohesion: 0.17
Nodes (13): applySettingsToUI(), loadApiUsage(), loadAuthState(), loadSettings(), logout(), openSettingsModal(), _setApiBar(), showView() (+5 more)

### Community 8 - "JWT Authentication"
Cohesion: 0.16
Nodes (15): auth_status(), create_access_token(), decode_token(), get_jwt_secret(), login(), LoginRequest, logout(), Authentication helpers: password verification, JWT creation/decoding, require_au (+7 more)

### Community 9 - "App Settings & Config"
Cohesion: 0.25
Nodes (15): AppSetting, SettingUpdate, complete_onboarding(), CompleteOnboardingBody, get_auto_fetch_setting(), list_settings(), Save onboarding preferences and mark onboarding as complete., Return the current pricing mode. Defaults to 'full' if not set. (+7 more)

### Community 10 - "Image Cache Service"
Cohesion: 0.33
Nodes (9): _cache_path(), _ct_path(), get_card_image(), Proxy card images, with a local disk cache to avoid repeat API calls.  Cache lay, Return (bytes, content_type) from disk cache, or None on miss., Write image bytes and content-type to disk cache., Return a card image. Served from disk cache when available; fetched and     cach, _read_cache() (+1 more)

### Community 11 - "Onboarding Wizard"
Cohesion: 0.32
Nodes (5): initOnboarding(), _initOnboardingControls(), _showOnboardingStep(), _updateOnboardingSummary(), _validateApiKey()

### Community 12 - "Currency Exchange Service"
Cohesion: 0.38
Nodes (6): get_rate(), _is_stale(), USD → EUR conversion using the Frankfurter API (ECB data, no key required).  The, Fetch a fresh USD→EUR rate and update the in-memory cache.     Returns the new r, Return the cached USD→EUR rate, refreshing if stale., refresh_rate()

### Community 13 - "Alembic Migration Engine"
Cohesion: 0.5
Nodes (2): run_async_migrations(), run_migrations_online()

### Community 14 - "Sets API Router"
Cohesion: 0.5
Nodes (4): get_set_image(), list_owned_sets(), list_sets(), _sets_are_stale()

### Community 15 - "Track Price Migration"
Cohesion: 0.5
Nodes (1): add track_price for_trade columns to collection  Revision ID: 0005features Revis

### Community 16 - "Initial Schema Migration"
Cohesion: 0.5
Nodes (1): initial schema  Revision ID: 0001 Revises: Create Date: 2024-01-01 00:00:00.0000

### Community 17 - "URL Rename Migration"
Cohesion: 0.5
Nodes (1): rename cardmarket_url to source_url on cards  Revision ID: 0004 Revises: 0003 Cr

### Community 18 - "Onboarding Settings Migration"
Cohesion: 0.5
Nodes (1): add onboarding settings  Revision ID: 0006onboarding Revises: 0005features Creat

### Community 19 - "App Settings Migration"
Cohesion: 0.5
Nodes (1): add app_settings table  Revision ID: c17d2f173cf7 Revises: 0004 Create Date: 202

### Community 20 - "Image URL Migration"
Cohesion: 0.5
Nodes (1): add image_url to cards  Revision ID: 0002 Revises: 0001 Create Date: 2026-04-10

### Community 21 - "Manual Cards Migration"
Cohesion: 0.5
Nodes (1): add source and cardmarket_url to cards  Revision ID: 0003 Revises: 0002 Create D

### Community 22 - "Rate Limiting & API Guard"
Cohesion: 0.67
Nodes (3): Known Issue: In-Memory Rate Limit Counter Resets on Restart, Phase 25 — Graceful 429 Rate Limit Handling, Phase 26 — Opt-In Auto-Load Full Sets

### Community 23 - "Image Disk Cache Docs"
Cohesion: 1.0
Nodes (2): Phase 27 — Server-Side Image Disk Cache + Lazy Loading, Image Disk Cache (./image_cache/)

### Community 24 - "Auth Header Pattern"
Cohesion: 1.0
Nodes (2): apiFetch() — Auth Header + 401 Retry Pattern, requireAuth() — Queued Promise Auth Gate

### Community 25 - "Routers Init"
Cohesion: 1.0
Nodes (0): 

### Community 26 - "Services Init"
Cohesion: 1.0
Nodes (0): 

### Community 27 - "Docker Workflow"
Cohesion: 1.0
Nodes (1): Docker Compose Workflow

### Community 28 - "pgAdmin Service"
Cohesion: 1.0
Nodes (1): pgAdmin Service

### Community 29 - "Project Scaffold"
Cohesion: 1.0
Nodes (1): Phase 1 — Project Scaffold

### Community 30 - "Sets View Phase"
Cohesion: 1.0
Nodes (1): Phase 11 — Tracked Sets View

### Community 31 - "Full Set Grid Phase"
Cohesion: 1.0
Nodes (1): Phase 24 — Full Set Card Grid with Ownership Styling

## Knowledge Gaps
- **85 isolated node(s):** `Return current in-memory PokéWallet API call counters.`, `add track_price for_trade columns to collection  Revision ID: 0005features Revis`, `initial schema  Revision ID: 0001 Revises: Create Date: 2024-01-01 00:00:00.0000`, `rename cardmarket_url to source_url on cards  Revision ID: 0004 Revises: 0003 Cr`, `add onboarding settings  Revision ID: 0006onboarding Revises: 0005features Creat` (+80 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Image Disk Cache Docs`** (2 nodes): `Phase 27 — Server-Side Image Disk Cache + Lazy Loading`, `Image Disk Cache (./image_cache/)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Auth Header Pattern`** (2 nodes): `apiFetch() — Auth Header + 401 Retry Pattern`, `requireAuth() — Queued Promise Auth Gate`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Routers Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Services Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Docker Workflow`** (1 nodes): `Docker Compose Workflow`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `pgAdmin Service`** (1 nodes): `pgAdmin Service`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Project Scaffold`** (1 nodes): `Phase 1 — Project Scaffold`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Sets View Phase`** (1 nodes): `Phase 11 — Tracked Sets View`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Full Set Grid Phase`** (1 nodes): `Phase 24 — Full Set Card Grid with Ownership Styling`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Set` connect `Backend Data & Routers` to `Backend Services & Scheduler`, `Frontend App Core`, `Onboarding Wizard`, `Sets API Router`?**
  _High betweenness centrality (0.209) - this node is a cross-community bridge._
- **Why does `renderCollectionGrouped()` connect `Frontend App Core` to `Backend Data & Routers`?**
  _High betweenness centrality (0.164) - this node is a cross-community bridge._
- **Why does `Card` connect `Backend Data & Routers` to `Image Cache Service`, `Backend Services & Scheduler`, `Manual Cards & PriceCharting`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Are the 32 inferred relationships involving `Card` (e.g. with `APScheduler nightly price refresh and weekly sets refresh.` and `Refresh prices for all cards in the collection. Runs at 02:00 daily.      In ful`) actually correct?**
  _`Card` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `Set` (e.g. with `APScheduler nightly price refresh and weekly sets refresh.` and `Refresh prices for all cards in the collection. Runs at 02:00 daily.      In ful`) actually correct?**
  _`Set` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `apiFetch()` (e.g. with `_validateApiKey()` and `_completeOnboarding()`) actually correct?**
  _`apiFetch()` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `CollectionEntry` (e.g. with `APScheduler nightly price refresh and weekly sets refresh.` and `Refresh prices for all cards in the collection. Runs at 02:00 daily.      In ful`) actually correct?**
  _`CollectionEntry` has 15 INFERRED edges - model-reasoned connections that need verification._