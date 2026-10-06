#!/usr/bin/env python3
"""Fetch OHLCV + RSI14 for watchlist tickers and update JSON data files.

Designed to run in GitHub Actions with yfinance. Preserves thesis / levels /
status fields; only refreshes market metrics and appends a history snapshot.
Never invents prices when fetch fails — keeps prior values and logs a warning.
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
        closes = hist["Close"]
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

        # Replace any existing history row for this ticker+day, else append
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

    # Keep GitHub Pages /docs mirror in sync (when present)
    if DOCS_DATA.is_dir():
        for name in ("watchlist.json", "history.json", "meta.json", "dropped.json"):
            src = DATA / name
            if src.exists():
                (DOCS_DATA / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        print("Synced docs/data/")

    print(f"Updated {updated}/{len(watchlist)} tickers for {day}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
