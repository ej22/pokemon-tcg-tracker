# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run inside Docker containers — there is no local Python environment.

```bash
# Start all services
docker compose up -d

# Rebuild backend after code changes
docker compose up -d --build backend

# Run database migrations
docker compose exec backend alembic upgrade head

# Create a new migration after model changes
docker compose exec backend alembic revision --autogenerate -m "description"

# Rollback one migration
docker compose exec backend alembic downgrade -1

# Check logs
docker compose logs backend --tail=50
docker compose logs -f backend     # follow

# Connect to PostgreSQL
docker compose exec db psql -U tcg_user -d tcg_tracker

# Run a one-off Python command in the backend container
docker compose exec backend python3 -c "..."
```

## Architecture

Four Docker services on a shared `tcg-net` bridge network:
- **db** (postgres:16) — PostgreSQL, internal only
- **backend** (Python 3.12 / FastAPI) → port 8014 (docs at `/docs`)
- **frontend** (Caddy 2) → port 3003; serves `frontend/` statically and proxies `/api/*` to `backend:8000`
- **pgadmin** → port 8015

### Backend layout

```
backend/
  main.py          FastAPI app + lifespan (starts/stops scheduler)
  database.py      Async engine + session factory
  models.py        SQLAlchemy ORM (sets, cards, collection, price_history, price_cache)
  schemas.py       Pydantic request/response models
  scheduler.py     APScheduler jobs (nightly 02:00 price refresh, Sunday 03:00 sets refresh)
  routers/
    collection.py  CRUD for user's collection
    prices.py      Price fetch + history + manual refresh
    sets.py        Sets list (weekly-cached) + set cards
    portfolio.py   Portfolio value aggregation
    search.py      PokéWallet search proxy + card metadata caching
  services/
    pokewallet.py  All PokéWallet HTTP calls + _normalise_card() + extract_cardmarket_prices()
    price_cache.py Cache TTL logic; get_price() is the single entry point for price data
```

### PokéWallet API response shape

The API nests card info — **do not assume flat fields**:
```json
{
  "id": "pk_...",
  "card_info": { "name": "...", "set_id": "2545", "set_code": "SWSD", ... },
  "cardmarket": { "prices": [{ "variant_type": "normal", "avg": 14.57, "trend": 14.21 }] }
}
```
`pokewallet._normalise_card()` flattens this. Always use normalised data downstream.

### Cache flow

```
get_price(card_api_id)
  → check price_cache table
  → if fresh (< PRICE_CACHE_TTL_HOURS, default 24h) → return DB data
  → else → GET /cards/{id} → parse cardmarket.prices[]
         → INSERT INTO price_history (append-only)
         → UPSERT price_cache (latest value)
```

### FK constraint: sets → cards

Cards have a FK to `sets`. When a card is cached before the sets list has been fetched, a placeholder `sets` row is auto-inserted using the `set_name` from the card response. The weekly sets refresh fills in the complete set data later.

### Scheduler

`AsyncIOScheduler` starts in the FastAPI `lifespan` context. Each job opens its own `AsyncSessionLocal()` — it never shares sessions with request handlers. Rate limit counters (`_calls_today`, `_calls_this_hour`) are module-level globals in `pokewallet.py`; they reset on container restart.

## Ports

| Port | Service |
|------|---------|
| 3003 | Frontend (Caddy) |
| 8014 | Backend API / Swagger UI |
| 8015 | pgAdmin |

These ports were chosen to avoid conflicts with existing services on the host. Do not change them without checking HANDOVER.md §7.
