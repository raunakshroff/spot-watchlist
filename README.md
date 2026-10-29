# Spot Watchlist

Modern NSE stock-tracking dashboard for **Raunak Shroff**. Dark technical UI, JSON-backed data, daily GitHub Action market updates. No spreadsheets.

**Live site:** https://raunakshroff.github.io/spot-watchlist/

**Repo:** https://github.com/raunakshroff/spot-watchlist

---

## Features

- **Overview** — status filters, ticker search, buy-zone / RSI alerts, expandable cards with levels + thesis + sparkline + sector badge
- **Sector** — group active names by NSE sector; filter pills per sector; same expandable cards
- **vs Nifty** — Daily / Weekly toggle; every available NSE index (broad, sectoral, thematic, strategy) plus BSE Sensex / BSE 100 / BSE 500, ranked by return with Nifty 50 as a highlighted row — above it outperformed, below it underperformed. Search, group filters, Above/Below filter, Ranked or By-group layout, ★ watchlist-linked filter; "My sectors" keeps the watchlist-sector cards. Config in `scripts/daily_update.py` (exclusions + BSE_INDICES).
- **Sovrenn** — Sovrenn Times highlights with price since first mention, buy-zone, RSI (separate from Active watchlist)
- **Events** — macro catalysts (seeded with DAC 26 Oct 2026 ~₹2.12 lakh Cr defence AoNs) with listed beneficiaries, % since event, buy-zone, RSI; daily auto-promotes near-breakout names to Active
- **History** — pick any logged market day and see that day's roster, prices, RSI, and whether anything was dropped
- **Dropped archive** — drop date, last price, sector, reason
- **Daily auto-update** — weekday cron at `45 10 * * 1-5` UTC (= **4:15 PM IST**), plus manual `workflow_dispatch`

## Stack

- Vite + React + TypeScript
- Recharts sparklines
- Data as JSON in `public/data/`
- GitHub Actions → GitHub Pages

## Data files

| File | Purpose |
|------|---------|
| `public/data/watchlist.json` | Active tracked names |
| `public/data/history.json` | Daily snapshots (one row per ticker per day) |
| `public/data/dropped.json` | Archived / dropped names |
| `public/data/meta.json` | Title, timezone, last update, how-to blurbs |
| `public/data/indices.json` | Nifty 50 benchmark + `indices[]` (all equity NSE indices + BSE Sensex/100/500 + a Nifty 50 benchmark row) + watchlist `sectors[]`, daily / weekly vs Nifty |
| `public/data/sovrenn.json` | Sovrenn Times highlighted companies (separate list) |
| `public/data/events.json` | Macro events + beneficiary companies (DAC defence AoNs, …); daily price/BZ refresh + auto-promote |

### Status values

`Active` · `Dip-buy` · `Breakout-watch` · `Holding` · `Watch` / `Watch-only` · `Wait-RBI`

---

## How to add a stock

1. Edit `public/data/watchlist.json` — append an object with `ticker`, `name`, `sector`, `status`, thesis, levels, etc.
2. Append a first row to `public/data/history.json` for today (`droppedThatDay: false`).
3. Commit & push to `main` (Pages rebuilds automatically).

Alternatively: open a GitHub issue, or tell Chief of Staff.

## How to drop a stock

1. Remove the ticker from `watchlist.json`.
2. Add an entry to `dropped.json` with `droppedDate`, `lastPrice`, `reason`, `priorStatus`.
3. Append a history row for that day with `"status": "Dropped"` and `"droppedThatDay": true`.
4. Commit & push.

## Daily Action

Workflow: `.github/workflows/daily-update.yml`

1. Checks out `main`
2. Installs Python deps from `scripts/requirements.txt` (`yfinance`, `pandas`)
3. Runs `scripts/daily_update.py` — refreshes price, daily %, RSI14, volume, vol vs 20d, sparkline; appends/replaces today's history rows; updates `meta.lastMarketUpdate`; refreshes `indices.json` (official NSE allIndices feed: daily % and close vs 1-week-ago close; Yahoo Finance fallback if NSE blocks the runner; BSE via Yahoo)
4. Commits with message `data: market update YYYY-MM-DD` and pushes (`contents: write`)

Manual run: **Actions → Daily market update → Run workflow**.

> Seed prices are as of **2026-10-06**. The Action never invents prices; if a fetch fails it keeps prior values and logs a warning.

## Local development

```bash
npm install
npm run dev
```

Build static site:

```bash
npm run build
npm run preview
```

Base path is `/spot-watchlist/` (GitHub Pages project site).

## Disclaimer

Research / personal tracking only — **not investment advice**.


## Deploy note (PAT / workflow scope)

The intended setup uses GitHub Actions workflows under `.github/workflows/`:

- `pages.yml` — build & deploy on push to `main`
- `daily-update.yml` — weekday cron market update

The token used to bootstrap this repo lacked the classic PAT **`workflow`** scope, so workflow files could not be pushed. **Identical YAML lives in `scripts/github-workflows/`.**

To activate Actions:

1. Add `workflow` scope to the PAT (or use a fine-grained token that can manage Actions), **or** paste the files via the GitHub UI:
   - Copy `scripts/github-workflows/pages.yml` → `.github/workflows/pages.yml`
   - Copy `scripts/github-workflows/daily-update.yml` → `.github/workflows/daily-update.yml`
2. Until then, the site is served from the **`/docs` folder on `main`** (GitHub Pages).
3. After workflows are in place, you can switch Pages source to **GitHub Actions** and optionally stop committing `docs/`.


## Price alerts

Optional `alerts` array on any `watchlist.json` entry (see `scripts/price_alerts.py`):

```json
{"id": "igil-pullback-381-386", "type": "range", "low": 381, "high": 386, "label": "Pullback entry zone 381–386", "status": "armed", "createdDate": "2026-10-29"}
{"id": "igil-breakout-419", "type": "closeAbove", "level": 419, "label": "Breakout: daily close above 419", "status": "armed", "createdDate": "2026-10-29"}
```

- `range` fires when the day's low ≤ `high` and high ≥ `low`; `closeAbove` / `closeBelow` fire on the daily close.
- Evaluated only by `daily_update.py` on today's completed bar (after 15:30 IST, or `--force-alerts`). A fired alert becomes `triggered` with `triggeredDate`, `triggeredPrice` (close), `dayLow`, `dayHigh`, `volVs20d`, stays visible, and never re-fires.
- The script prints `CHAT_NOTE_ALERTS:` lines (hits + armed count) for the daily chat note.
- Dry run against live data: `python scripts/price_alerts.py IGIL.NS` (writes nothing).
