# PokéTCG Tracker

![Collection Page](/frontend.png "Frontend")

A self-hosted Pokémon TCG collection tracker. Log your card hits, track CardMarket EUR prices, and watch your portfolio value grow — all running locally in Docker.

## Architecture

| Service    | Image                | Role                                      |
|------------|----------------------|-------------------------------------------|
| `db`       | postgres:16-alpine   | PostgreSQL database                       |
| `backend`  | Python 3.12 / FastAPI| REST API, price cache, APScheduler jobs   |
| `frontend` | caddy:2-alpine       | Serves static HTML/JS, proxies `/api/*`   |
| `pgadmin`  | dpage/pgadmin4       | Database admin UI                         |

## Prerequisites

- Docker & Docker Compose v2
- A [PokéWallet](https://pokewallet.io) API key
- Ports 3003, 8014, and 8015 free on your server

## Setup

```bash
# 1. Clone
git clone https://github.com/ej22/pokemon-tcg-tracker.git
cd pokemon-tcg-tracker

# 2. Configure environment
cp .env.example .env
# Edit .env — set POKEWALLET_API_KEY and change the default passwords

# 3. Start services
docker compose up -d

# 4. Run database migrations
docker compose exec backend alembic upgrade head

# 5. Open the app
open http://localhost:3003
```

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

## API Endpoints

| Method | Path                                | Description                                   |
|--------|-------------------------------------|-----------------------------------------------|
| GET    | `/api/collection`                   | List all collection entries with prices       |
| POST   | `/api/collection`                   | Add a card to the collection                  |
| PUT    | `/api/collection/{id}`              | Update a collection entry                     |
| DELETE | `/api/collection/{id}`              | Remove a card from the collection             |
| GET    | `/api/search?q={query}`             | Search for cards via PokéWallet               |
| GET    | `/api/sets`                         | List all cached sets                          |
| GET    | `/api/sets/mine`                    | List only sets the user has tracked cards in  |
| GET    | `/api/sets/{set_id}/cards`          | List cards in a set                           |
| GET    | `/api/sets/{set_code}/image`        | Proxy set logo artwork from PokéWallet        |
| GET    | `/api/prices/{card_api_id}`         | Get latest cached prices for a card           |
| GET    | `/api/prices/{card_api_id}/history` | Full price history for a card                 |
| POST   | `/api/prices/refresh`               | Force-refresh prices for all collection cards |
| GET    | `/api/portfolio/summary`            | Portfolio value summary                       |
| GET    | `/api/images/{card_api_id}`         | Proxy card artwork from PokéWallet (browser-cacheable) |
| GET    | `/api/health`                       | Health check                                  |

Full interactive docs: `http://localhost:8014/docs`

## UI

The frontend is a single-page vanilla HTML/JS/CSS app served by Caddy — no build step.

**Collection view** — Netflix-style poster grid. Each card displays its artwork (fetched via the image proxy), condition chip, quantity badge, and price in a bottom gradient overlay. Hover reveals edit and delete action buttons. Clicking the card body opens the edit modal.

**Portfolio view** — KPI summary cards (estimated value, card count, priced count) and a Chart.js line chart showing portfolio value over time, plus a value-by-set breakdown table.

**Sets view** — Poster grid of sets the user has tracked cards in. Each set is a 16:9 landscape card showing the official set logo (fetched via the image proxy), with the set name, release date, card count, and owned-card count. Clicking a set loads its cards as a portrait poster grid with the same artwork display; hover reveals an Add to Collection button for each card.

**Image proxy** — Card artwork is served via `GET /api/images/{card_api_id}`. The backend fetches the image from PokéWallet using the server-side API key and returns it with `Cache-Control: public, max-age=86400` so browsers cache each image for 24 hours — subsequent page loads make no API calls for images.

## How the Price Cache Works

Prices are fetched from CardMarket (EUR) via the PokéWallet API and stored locally in two tables:

- **`price_cache`** — one row per card/variant/source combination, updated in place. Used for fast lookups.
- **`price_history`** — every price fetch appended as a new row, never overwritten. Used for historical charting.

Before any API call the backend checks `price_cache`:
- If a record exists and `last_fetched_at` is within `PRICE_CACHE_TTL_HOURS` (default 24h) → return the cached value, no API call made.
- If the record is missing or older than the TTL → call PokéWallet, store the result, return it.

### Rate limit protection

PokéWallet free tier allows ~1,000 calls/day and ~100/hour. The backend:
- Logs a warning when 800 daily calls are reached
- Stops making calls when 80 hourly calls are reached
- Resets both counters on schedule (hourly / daily)
- If the nightly scheduler hits the hourly limit mid-run it pauses and resumes the next night

## PokéWallet Data Gaps

PokéWallet's database does not contain every card. Newer sets in particular may be listed in the sets index but only partially populated. If a card search returns no results, it means PokéWallet hasn't added it yet — this is outside the app's control. You can periodically check whether the set's card count in the Sets browser has grown to confirm when new cards are added.

## Scheduled Jobs

| Job                    | Schedule           | What it does                              |
|------------------------|--------------------|-------------------------------------------|
| Nightly price refresh  | Every day at 02:00 | Force-refreshes prices for all owned cards|
| Weekly sets refresh    | Sundays at 03:00   | Re-fetches the full sets list             |
| Hourly counter reset   | Every hour :00     | Resets the hourly API call counter        |
| Daily counter reset    | Every day at 00:00 | Resets the daily API call counter         |

## Manual Price Refresh

From the Portfolio view, click **↻ Refresh Prices**. This calls `POST /api/prices/refresh` and force-refreshes all cards in your collection regardless of cache TTL.

Via curl:
```bash
curl -X POST http://localhost:8014/api/prices/refresh
```

## Database Backup

```bash
docker compose exec db pg_dump -U tcg_user tcg_tracker > backup_$(date +%Y%m%d).sql
```

Restore:
```bash
cat backup_20240101.sql | docker compose exec -T db psql -U tcg_user tcg_tracker
```

## Alembic Migrations

```bash
# Apply all pending migrations
docker compose exec backend alembic upgrade head

# Check current revision
docker compose exec backend alembic current

# Create a new migration
docker compose exec backend alembic revision --autogenerate -m "description"
```

## Port Reference

| Port  | Service         | URL                        |
|-------|-----------------|----------------------------|
| 3003  | Frontend (Caddy)| http://localhost:3003       |
| 8014  | Backend (FastAPI)| http://localhost:8014/docs |
| 8015  | pgAdmin         | http://localhost:8015       |
