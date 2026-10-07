# Spot Watchlist

Modern NSE stock-tracking dashboard for **Raunak Shroff**. Dark technical UI, JSON-backed data, daily GitHub Action market updates. No spreadsheets.

**Live site:** https://raunakshroff.github.io/spot-watchlist/

**Repo:** https://github.com/raunakshroff/spot-watchlist

---

## Features

- **Overview** — status filters, ticker search, buy-zone / RSI alerts, expandable cards with levels + thesis + sparkline + sector badge
- **Sector** — group active names by NSE sector; filter pills per sector; same expandable cards
- **vs Nifty** — Daily / Weekly toggle; every NSE equity index (Broad Market, Sectoral, Thematic, Strategy) plus BSE Sensex / 100 / 500 ranked above or below Nifty 50. Search, group filters, Above/Below filter, Ranked or By-group layout, ★ watchlist-linked filter. "My sectors" keeps the watchlist-sector cards.
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
| `public/data/indices.json` | Nifty 50 benchmark + `indices[]` (all NSE equity indices + BSE) + watchlist `sectors[]`, daily / weekly vs Nifty |

### Status values

`Active` · `Dip-buy` · `Breakout-watch` · `Holding` · `Watch-only` · `Wait-RBI`

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

