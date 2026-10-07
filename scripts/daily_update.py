#!/usr/bin/env python3
"""Fetch OHLCV + RSI14 for watchlist tickers and update JSON data files.

Also refreshes public/data/indices.json — Nifty 50 vs sector indices (or
watchlist equal-weight fallback). Designed to run in GitHub Actions with
yfinance. Preserves thesis / levels / status fields; only refreshes market
metrics and appends a history snapshot. Never invents prices when fetch fails
— keeps prior values and logs a warning.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import yfinance as yf
except ImportError:
    print("yfinance not installed. pip install yfinance pandas", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public" / "data"
DOCS_DATA = ROOT / "docs" / "data"
IST = ZoneInfo("Asia/Kolkata")

# Watchlist sector → preferred official NSE index (Yahoo Finance)
SECTOR_INDEX_MAP = [
    {"sector": "Pharma", "indexName": "Nifty Pharma", "symbol": "^CNXPHARMA"},
    {"sector": "IT / Cloud / Data center", "indexName": "Nifty IT", "symbol": "^CNXIT"},
    {"sector": "Auto Ancillaries", "indexName": "Nifty Auto", "symbol": "^CNXAUTO"},
    {"sector": "Capital Goods / Infrastructure", "indexName": "Nifty Infra", "symbol": "^CNXINFRA"},
    {"sector": "Capital Goods / Industrial", "indexName": "Nifty Infra", "symbol": "^CNXINFRA"},
    {"sector": "Defence / Aerospace", "indexName": None, "symbol": None},
    {"sector": "FMCG", "indexName": "Nifty FMCG", "symbol": "^CNXFMCG"},
]

DATA_FILES = (
    "watchlist.json",
    "history.json",
    "meta.json",
    "dropped.json",
    "indices.json",
)


def load(name: str):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


def save(name: str, obj) -> None:
    with open(DATA / name, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def rsi14(closes) -> float | None:
    if closes is None or len(closes) < 15:
        return None
    deltas = closes.diff().dropna()
    if len(deltas) < 14:
        return None
    gains = deltas.clip(lower=0)
    losses = -deltas.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, math.nan)
    rsi = 100 - (100 / (1 + rs))
    val = float(rsi.iloc[-1])
    return None if math.isnan(val) else round(val, 1)


def sparkline(closes, n: int = 10) -> list[float]:
    if closes is None or len(closes) == 0:
        return []
    vals = [float(x) for x in closes.tail(n).tolist() if x == x]
    return [round(v, 2) for v in vals]


def fetch_metrics(ticker: str) -> dict | None:
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="3mo", auto_adjust=True)
        if hist is None or hist.empty:
            print(f"WARN: no history for {ticker}")
            return None
        closes = hist["Close"].dropna()
        if closes.empty:
            print(f"WARN: no valid closes for {ticker}")
            return None
        volumes = hist["Volume"]
        last = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) > 1 else last
        daily_pct = ((last - prev) / prev) * 100 if prev else None
        vol = float(volumes.iloc[-1]) if "Volume" in hist else None
        vol_ma = float(volumes.tail(20).mean()) if len(volumes) >= 20 else None
        vol_vs = round(vol / vol_ma, 2) if vol and vol_ma else None
        return {
            "price": round(last, 2),
            "dailyPct": round(daily_pct, 2) if daily_pct is not None else None,
            "rsi14": rsi14(closes),
            "volume": int(vol) if vol == vol else None,
            "volVs20d": vol_vs,
            "sparkline": sparkline(closes),
        }
    except Exception as e:  # noqa: BLE001
        print(f"WARN: fetch failed for {ticker}: {e}")
        return None


def today_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def pct(a, b) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return round((a / b - 1.0) * 100, 2)


def avg(xs) -> float | None:
    vals = [x for x in xs if x is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def fetch_official_index(symbol: str) -> dict:
    """Daily/weekly from Yahoo history + fast_info overlay (session last print)."""
    t = yf.Ticker(symbol)
    closes: list[float] = []
    try:
        h = t.history(period="1mo", auto_adjust=True)
        if h is not None and not h.empty:
            closes = [float(x) for x in h["Close"].dropna().tolist()]
    except Exception as e:  # noqa: BLE001
        print(f"WARN: index history {symbol}: {e}")

    fi_last = fi_prev = None
    try:
        fi = t.fast_info
        if getattr(fi, "last_price", None) is not None:
            fi_last = float(fi.last_price)
        if getattr(fi, "previous_close", None) is not None:
            fi_prev = float(fi.previous_close)
    except Exception as e:  # noqa: BLE001
        print(f"WARN: index fast_info {symbol}: {e}")

    if fi_last is not None:
        if not closes:
            closes = [fi_prev, fi_last] if fi_prev is not None else [fi_last]
        elif abs(fi_last - closes[-1]) / max(abs(closes[-1]), 1e-9) > 1e-4:
            closes.append(fi_last)

    daily = pct(closes[-1], closes[-2]) if len(closes) >= 2 else None
    if daily is None and fi_last is not None and fi_prev is not None:
        daily = pct(fi_last, fi_prev)
        if len(closes) < 2:
            closes = [fi_prev, fi_last]

    weekly = pct(closes[-1], closes[-6]) if len(closes) >= 6 else None
    last = round(closes[-1], 2) if closes else (round(fi_last, 2) if fi_last else None)

    return {
        "last": last,
        "dailyPct": daily,
        "weeklyPct": weekly,
        "bars": len(closes),
        "hasDaily": daily is not None,
        "hasWeekly": weekly is not None,
    }


def watchlist_sector_returns(stocks: list[dict]) -> dict:
    dailies, weeklies = [], []
    for s in stocks:
        if s.get("dailyPct") is not None:
            dailies.append(float(s["dailyPct"]))
        spark = s.get("sparkline") or []
        if len(spark) >= 6 and spark[-6]:
            weeklies.append(pct(float(spark[-1]), float(spark[-6])))
    return {"dailyPct": avg(dailies), "weeklyPct": avg(weeklies)}


def build_indices(watchlist: list[dict], as_of: str) -> dict | None:
    by_sector: dict[str, list] = {}
    for s in watchlist:
        by_sector.setdefault(s.get("sector") or "Other", []).append(s)

    try:
        bench_raw = fetch_official_index("^NSEI")
    except Exception as e:  # noqa: BLE001
        print(f"WARN: Nifty 50 fetch failed: {e}")
        return None
    if not bench_raw.get("hasDaily"):
        print(f"WARN: Nifty 50 daily missing: {bench_raw}")
        return None

    benchmark = {
        "name": "Nifty 50",
        "symbol": "^NSEI",
        "last": bench_raw["last"],
        "dailyPct": bench_raw["dailyPct"],
        "weeklyPct": bench_raw["weeklyPct"],
        "source": "official",
        "bars": bench_raw["bars"],
    }

    active = [m for m in SECTOR_INDEX_MAP if m["sector"] in by_sector]
    mapped = {m["sector"] for m in SECTOR_INDEX_MAP}
    for sec in by_sector:
        if sec not in mapped:
            active.append({"sector": sec, "indexName": None, "symbol": None})

    sectors_out = []
    for m in active:
        sec = m["sector"]
        names = by_sector[sec]
        tickers = [s["ticker"] for s in names]
        wl = watchlist_sector_returns(names)

        off = fetch_official_index(m["symbol"]) if m["symbol"] else None

        daily_src = weekly_src = "watchlist"
        daily = wl["dailyPct"]
        weekly = wl["weeklyPct"]
        last = None
        index_name = None
        symbol = None
        notes: list[str] = []

        if off and off.get("hasDaily"):
            daily = off["dailyPct"]
            daily_src = "official"
            last = off["last"]
            index_name = m["indexName"]
            symbol = m["symbol"]
        if off and off.get("hasWeekly"):
            weekly = off["weeklyPct"]
            weekly_src = "official"
            last = off["last"]
            index_name = m["indexName"]
            symbol = m["symbol"]

        if daily_src == "watchlist" and weekly_src == "watchlist":
            notes.append("Watchlist sector vs Nifty (not official index)")
        else:
            if daily_src == "watchlist":
                notes.append("Daily: watchlist equal-weight (official history incomplete)")
            if weekly_src == "watchlist":
                notes.append("Weekly: watchlist equal-weight (official history incomplete)")
        if sec == "Capital Goods / Industrial" and symbol == "^CNXINFRA":
            notes.append(
                "Nifty Infra used as closest official proxy for Capital Goods / Industrial"
            )

        if daily_src == "official" and weekly_src == "official":
            source = "official"
        elif daily_src == "watchlist" and weekly_src == "watchlist":
            source = "watchlist"
        else:
            source = "mixed"

        vs_d = (
            round(daily - benchmark["dailyPct"], 2)
            if daily is not None and benchmark["dailyPct"] is not None
            else None
        )
        vs_w = (
            round(weekly - benchmark["weeklyPct"], 2)
            if weekly is not None and benchmark["weeklyPct"] is not None
            else None
        )

        sectors_out.append(
            {
                "sector": sec,
                "indexName": index_name,
                "symbol": symbol,
                "source": source,
                "dailySource": daily_src,
                "weeklySource": weekly_src,
                "last": last,
                "dailyPct": daily,
                "weeklyPct": weekly,
                "vsNiftyDaily": vs_d,
                "vsNiftyWeekly": vs_w,
                "watchlistTickers": tickers,
                "watchlistCount": len(tickers),
                "note": "; ".join(notes) if notes else None,
            }
        )

    return {
        "asOf": as_of,
        "timezone": "Asia/Kolkata",
        "lastRunUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "benchmark": benchmark,
        "sectors": sectors_out,
        "disclaimer": (
            "Research / personal tracking only — not investment advice. "
            "Official NSE sector indices via Yahoo Finance when available; "
            "otherwise equal-weight watchlist average."
        ),
    }


def sync_docs_data() -> None:
    if not DOCS_DATA.is_dir():
        return
    for name in DATA_FILES:
        src = DATA / name
        if src.exists():
            (DOCS_DATA / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    print("Synced docs/data/")


def main() -> int:
    watchlist = load("watchlist.json")
    history = load("history.json")
    meta = load("meta.json")
    day = today_ist()

    updated = 0
    for stock in watchlist:
        ticker = stock["ticker"]
        metrics = fetch_metrics(ticker)
        if not metrics:
            print(f"Keeping prior metrics for {ticker}")
            continue
        stock["price"] = metrics["price"]
        stock["dailyPct"] = metrics["dailyPct"]
        stock["rsi14"] = metrics["rsi14"]
        stock["volume"] = metrics["volume"]
        stock["volVs20d"] = metrics["volVs20d"]
        stock["sparkline"] = metrics["sparkline"]
        stock["lastUpdated"] = day
        updated += 1

        history = [
            h for h in history if not (h.get("date") == day and h.get("ticker") == ticker)
        ]
        history.append(
            {
                "date": day,
                "ticker": ticker,
                "name": stock.get("name"),
                "status": stock.get("status"),
                "price": stock.get("price"),
                "dailyPct": stock.get("dailyPct"),
                "rsi14": stock.get("rsi14"),
                "volume": stock.get("volume"),
                "volVs20d": stock.get("volVs20d"),
                "support": stock.get("support"),
                "resistance": stock.get("resistance"),
                "buyZoneLevels": stock.get("buyZoneLevels"),
                "stop": stock.get("stop"),
                "notes": f"Auto market update {day}",
                "droppedThatDay": False,
            }
        )

    history.sort(key=lambda h: (h.get("date", ""), h.get("ticker", "")))
    meta["lastMarketUpdate"] = day
    meta["lastRunUtc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    save("watchlist.json", watchlist)
    save("history.json", history)
    save("meta.json", meta)

    indices = build_indices(watchlist, as_of=day)
    if indices:
        save("indices.json", indices)
        print(f"Updated indices.json ({len(indices['sectors'])} sectors vs Nifty 50)")
    else:
        print("WARN: skipped indices.json refresh")

    sync_docs_data()

    print(f"Updated {updated}/{len(watchlist)} tickers for {day}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
