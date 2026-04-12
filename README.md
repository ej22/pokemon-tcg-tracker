# PokéTCG Tracker

![Collection Page](/frontend.png "Collection view")

A self-hosted app for tracking your Pokémon TCG card collection. Add your cards, see them displayed as a visual poster grid, and optionally track their CardMarket market values over time — all running locally on your own machine.

---

## What it does

- **Collection** — add cards by searching by name, then log condition, language, variant, and purchase price. Cards are displayed as a poster grid with their artwork.
- **Sets view** — browse which sets you have cards in. See how many cards from each set you own.
- **Portfolio** — see your collection's estimated EUR market value, with a chart showing how it's changed over time.
- **Two modes** — run in *full mode* (prices fetched automatically from CardMarket) or *collection-only mode* (no price lookups, minimal API usage — just track what you own visually).
- **Grouped view** — browse your collection grouped by set, with collapsible sections. Each set row scrolls horizontally, or switch to a grid layout in settings.
- **Promo cards** — for cards not in PokéWallet, add them by pasting a PriceCharting URL.
- **Fully self-hosted** — runs in Docker, no external accounts needed beyond a free PokéWallet API key.

---

## What you need

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2
- A free API key from [pokewallet.io](https://pokewallet.io)
- Ports **3003**, **8014**, and **8015** free on your machine

---

## Getting started

**1. Clone the repo**
```bash
git clone https://github.com/ej22/pokemon-tcg-tracker.git
cd pokemon-tcg-tracker
```

**2. Set up your environment**
```bash
cp .env.example .env
```
Open `.env` and fill in your values — at minimum, set `POKEWALLET_API_KEY` and change the database passwords from their defaults.

**3. Start the app**
```bash
docker compose up -d
docker compose exec backend alembic upgrade head
```

**4. Open it in your browser**
```
http://localhost:3003
```

That's it. The app runs in the background and will keep prices up to date automatically overnight.

---

## Adding cards

1. Click **Add Card** in the collection view.
2. Search for the card by name — results come from PokéWallet's database.
3. Pick the card, fill in condition, variant, and any other details.
4. Click **Add to Collection**.

If the card isn't in PokéWallet (some promos and newer sets), click **Add by PriceCharting URL** instead and paste the card's page URL from pricecharting.com.

---

## Settings

Click the gear icon at the bottom of the sidebar to open settings.

| Setting | What it does |
|---------|-------------|
| **Full mode** | Prices are fetched when you add a card and refreshed nightly at 02:00. Enables portfolio value and P&L tracking. Uses your PokéWallet API quota. |
| **Collection only** | No price fetching at all. Use this if you just want to keep track of what you own without hitting API limits. |
| **Grouped layout — Horizontal** | Cards within each set section scroll horizontally (default). |
| **Grouped layout — Grid** | Cards within each set section wrap into a full grid. |

---

## Backup

```bash
docker compose exec db pg_dump -U tcg_user tcg_tracker > backup_$(date +%Y%m%d).sql
```

---

## Ports

| Port | What's there |
|------|-------------|
| 3003 | The app |
| 8014 | Backend API + Swagger docs (`/docs`) |
| 8015 | pgAdmin (database browser) |

---

## For developers

See [TECHNICAL.md](TECHNICAL.md) for architecture details, API reference, environment variables, migration commands, and build notes.

---

## License

This project is released under the [MIT License](LICENSE). You are free to use, modify, and distribute it for any purpose.
