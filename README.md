# PokéTCG Tracker

![Collection Page](/frontend.png "Collection view")

A self-hosted app for tracking your Pokémon TCG card collection. Add your cards, see them displayed as a visual poster grid, and optionally track their CardMarket market values over time — all running locally on your own machine.

---

## What it does

- **Collection** — add cards by searching by name, then log condition, language, variant, and purchase price. Cards are displayed as a poster grid with their artwork.
- **Sets view** — browse which sets you have cards in, see how many cards from each set you own, and bulk-insert missing-card placeholders with one button.
- **Portfolio** — see your collection's estimated EUR market value, with a chart showing how it's changed over time.
- **Two modes** — run in *full mode* (prices fetched automatically from CardMarket) or *collection-only mode* (no price lookups — just track what you own, with optional per-card price tracking for the cards that matter).
- **Grouped view** — browse your collection grouped by set, with collapsible sections showing owned/missing counts. Sort cards within each section by set number or rarity (ascending or descending). Drag sets into a custom order using the reorder button, or use ↑/↓ buttons on touch devices.
- **Card view** — click any card in your collection to open a full-screen view of the artwork alongside the card's details, pricing, and P&L. An Edit button opens the edit modal from there.
- **Missing cards** — add qty=0 placeholders for cards you don't own yet. They show in a greyed-out "Missing" state so you can see exactly what's left to complete a set.
- **Trade Binder** — mark cards as available for trade. A dedicated Trade Binder view shows them all in one place with their current market values.
- **Promo cards** — for cards not in PokéWallet, add them by pasting a PriceCharting URL.
- **Optional login** — enable password protection by setting three env vars. Leave them unset for open access on a private network.
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

To enable login protection, also set these three vars (leave them out for open access):
```
AUTH_USERNAME=your_username
AUTH_PASSWORD=your_password
JWT_SECRET_KEY=any_random_string
```

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

**Adding a whole set at once** — open the set in the Sets view and click **Track all missing**. This inserts qty=0 placeholders for every card in the set you don't already own, so you have a complete roster to fill in.

**Marking a quantity of 0** — if you know a card exists but don't own it yet, you can add it with quantity 0 directly. It appears greyed out in your collection with a "Missing" badge.

---

## Grouped view controls

When the collection is in grouped mode, three extra controls appear in the header bar:

- **Sort dropdown** — sort cards within every set section simultaneously. Options: set number ascending/descending, or rarity low-to-high/high-to-low (with set number as a tiebreaker). Your choice is remembered across reloads.
- **Reorder sets button** (requires login if auth is enabled) — activates reorder mode. All sections collapse for easy navigation, then on desktop you can drag them into any order using the grip handle on the left of each header. On touch devices, ↑/↓ arrow buttons appear on the right instead. Exiting reorder mode restores each section to its previous collapsed/expanded state. Your custom order persists across reloads.
- **Show/Hide missing** — toggles visibility of qty=0 placeholder cards across the whole collection.

---

## Trade Binder

Click the arrows icon on any collection card to mark it as available for trade. Marked cards get a **TRADE** badge and appear in the **Trade Binder** tab, which shows all your tradeable cards in one place along with their current market values and a total estimated value.

To remove a card from the binder, click the trade icon again (from either the collection view or the Trade Binder itself).

---

## Settings

Click the gear icon at the bottom of the sidebar to open settings.

| Setting | What it does |
|---------|-------------|
| **Full mode** | Prices are fetched when you add a card and refreshed nightly at 02:00. Enables portfolio value and P&L tracking. Uses your PokéWallet API quota. |
| **Collection only** | No automatic price fetching. Use this if you just want to track what you own. You can still opt individual cards into price tracking using the star icon, and trade-binder cards are always priced. |
| **Grouped layout — Horizontal** | Cards within each set section wrap across rows (default). |
| **Grouped layout — Grid** | Cards within each set section use an even auto-fill grid. |
| **Auto-load full sets** | When opening a set in the Sets view, automatically fetch all cards from PokéWallet to show the complete roster (not just cached cards). Off by default to conserve API quota. |
| **Set card images** | Show or hide card artwork in the Sets view. Hiding images avoids API calls when browsing sets. |

### Per-card price tracking (collection-only mode)

In collection-only mode, click the **star icon** on any card to enable price tracking for that card individually. Useful for high-value cards or anything you're thinking of selling, without enabling full pricing for your whole collection.

Cards marked for trade are always priced regardless of this setting.

---

## Authentication

By default the app is open — no login required. This is fine for a private network (e.g. behind Tailscale or a VPN).

To add password protection, set these three vars in your `.env` before starting:

| Variable | Purpose |
|----------|---------|
| `AUTH_USERNAME` | Your login username |
| `AUTH_PASSWORD` | Your login password |
| `JWT_SECRET_KEY` | Any random string used to sign tokens — change it to log everyone out |

Once set, all write actions (adding, editing, deleting cards; changing settings) will prompt for login. Read-only views (browsing your collection, portfolio, sets) remain public.

To disable auth again, remove or comment out `AUTH_USERNAME` and restart.

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
