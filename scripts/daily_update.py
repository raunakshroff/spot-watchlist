#!/usr/bin/env python3
"""Fetch OHLCV + RSI14 for watchlist tickers and update JSON data files.

Also refreshes public/data/indices.json — Nifty 50 vs every available NSE
index (broad, sectoral, thematic, strategy) from the official NSE allIndices
feed with Yahoo Finance fallback, plus BSE Sensex / BSE 100 / BSE 500. Designed to run in GitHub Actions with
yfinance. Preserves thesis / levels / status fields; only refreshes market
metrics and appends a history snapshot. Never invents prices when fetch fails
— keeps prior values and logs a warning.
"""

from __future__ import annotations

import json
import math
import re
import sys
import time
from datetime import datetime, timedelta, timezone
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

# ---------------------------------------------------------------------------
# Index universe (vs Nifty 50)
#
# Primary source: NSE allIndices API (official last / % change / 1-week-ago
# close for every NSE index). Fallback: Yahoo Finance symbols verified to
# return data (daily always; weekly only where Yahoo has daily history).
# BSE benchmarks (Sensex, BSE 100, BSE 500) come from Yahoo.
# ---------------------------------------------------------------------------

NSE_ALL_INDICES_URL = "https://www.nseindia.com/api/allIndices"
BENCHMARK_NSE = "NIFTY 50"

# Watchlist sector -> NSE indexSymbol used as its official proxy
SECTOR_INDEX_MAP = [
    {"sector": "Pharma", "nseSymbol": "NIFTY PHARMA"},
    {"sector": "IT / Cloud / Data center", "nseSymbol": "NIFTY IT"},
    {"sector": "Auto Ancillaries", "nseSymbol": "NIFTY AUTO"},
    {"sector": "Capital Goods / Infrastructure", "nseSymbol": "NIFTY INFRA"},
    {
        "sector": "Capital Goods / Industrial",
        "nseSymbol": "NIFTY INFRA",
        "note": "Nifty Infrastructure used as closest official proxy for Capital Goods / Industrial",
    },
    {"sector": "Defence / Aerospace", "nseSymbol": "NIFTY IND DEFENCE"},
    {"sector": "FMCG", "nseSymbol": "NIFTY FMCG"},
    {"sector": "Private Bank", "nseSymbol": "NIFTY PVT BANK"},
]

# ---------------------------------------------------------------------------
# Curated MAJOR index board for the vs Nifty tab — edit here.
#
# Only indices listed in MAJOR_INDICES (plus BSE_INDICES) are tracked; every
# other index in NSE's feed is dropped. To bring one back, add a row:
#   (NSE indexSymbol, display name, group)
# indexSymbol = the `indexSymbol` field in https://www.nseindia.com/api/allIndices
# ---------------------------------------------------------------------------
MAJOR_INDICES: list[tuple[str, str, str]] = [
    # Benchmarks / broad market (Nifty 50 itself is added as the benchmark row)
    ("NIFTY NEXT 50", "Nifty Next 50", "Broad Market"),
    ("NIFTY 100", "Nifty 100", "Broad Market"),
    ("NIFTY 500", "Nifty 500", "Broad Market"),
    ("NIFTY MIDCAP 100", "Nifty Midcap 100", "Broad Market"),
    ("NIFTY MIDCAP 150", "Nifty Midcap 150", "Broad Market"),
    ("NIFTY SMLCAP 100", "Nifty Smallcap 100", "Broad Market"),
    ("NIFTY SMLCAP 250", "Nifty Smallcap 250", "Broad Market"),
    # Sectoral
    ("NIFTY BANK", "Nifty Bank", "Sectoral"),
    ("NIFTY PSU BANK", "Nifty PSU Bank", "Sectoral"),
    ("NIFTY PVT BANK", "Nifty Private Bank", "Sectoral"),
    ("NIFTY FIN SERVICE", "Nifty Financial Services", "Sectoral"),
    ("NIFTY AUTO", "Nifty Auto", "Sectoral"),
    ("NIFTY FMCG", "Nifty FMCG", "Sectoral"),
    ("NIFTY IT", "Nifty IT", "Sectoral"),
    ("NIFTY MEDIA", "Nifty Media", "Sectoral"),
    ("NIFTY METAL", "Nifty Metal", "Sectoral"),
    ("NIFTY PHARMA", "Nifty Pharma", "Sectoral"),
    ("NIFTY HEALTHCARE", "Nifty Healthcare", "Sectoral"),
    ("NIFTY REALTY", "Nifty Realty", "Sectoral"),
    ("NIFTY CONSR DURBL", "Nifty Consumer Durables", "Sectoral"),
    ("NIFTY OIL AND GAS", "Nifty Oil & Gas", "Sectoral"),
    ("NIFTY CHEMICALS", "Nifty Chemicals", "Sectoral"),  # NSE lists under Sectoral
    # Key thematic
    ("NIFTY ENERGY", "Nifty Energy", "Thematic"),
    ("NIFTY INFRA", "Nifty Infrastructure", "Thematic"),
    ("NIFTY COMMODITIES", "Nifty Commodities", "Thematic"),
    ("NIFTY CPSE", "Nifty CPSE", "Thematic"),
    ("NIFTY PSE", "Nifty PSE", "Thematic"),
    ("NIFTY CONSUMPTION", "Nifty India Consumption", "Thematic"),
    ("NIFTY IND DEFENCE", "Nifty India Defence", "Thematic"),
    ("NIFTY CAPITAL MKT", "Nifty Capital Markets", "Thematic"),
    ("NIFTY MNC", "Nifty MNC", "Thematic"),
    ("NIFTY INDIA MFG", "Nifty India Manufacturing", "Thematic"),
]

# BSE rows (Yahoo Finance). Add {"name": "BSE 100", "symbol": "BSE-100.BO",
# "group": "Broad Market"} etc. to bring others back.
BSE_INDICES = [
    {"name": "BSE Sensex", "symbol": "^BSESN", "group": "Broad Market"},
]

# Deliberately NOT tracked (documentation; anything absent from MAJOR_INDICES
# is dropped automatically): fixed income / G-sec, India VIX, Nifty50
# leverage / inverse / dividend points, strategy & factor indices (Alpha,
# Momentum, Quality, Value, Low Vol, Equal Weight, High Beta, ...), ESG /
# Shariah variants, corporate-group indices (Tata, MAATR, Conglomerate), IPO,
# SME Emerge, niche thematics, extra broad/size cuts, BSE 100 / BSE 500.

# NSE indexSymbol -> Yahoo symbol (verified 2026-10-07); used only if NSE is
# unreachable. Midcap 150 / Smallcap 250 have no Yahoo symbol (NSE-only).
YAHOO_SYMBOLS: dict[str, str] = {
    "NIFTY 50": "^NSEI",
    "NIFTY NEXT 50": "^NSMIDCP",
    "NIFTY 100": "^CNX100",
    "NIFTY 500": "^CRSLDX",
    "NIFTY MIDCAP 100": "NIFTY_MIDCAP_100.NS",
    "NIFTY SMLCAP 100": "^CNXSC",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY PSU BANK": "^CNXPSUBANK",
    "NIFTY PVT BANK": "NIFTY_PVT_BANK.NS",
    "NIFTY FIN SERVICE": "NIFTY_FIN_SERVICE.NS",
    "NIFTY AUTO": "^CNXAUTO",
    "NIFTY FMCG": "^CNXFMCG",
    "NIFTY IT": "^CNXIT",
    "NIFTY MEDIA": "^CNXMEDIA",
    "NIFTY METAL": "^CNXMETAL",
    "NIFTY PHARMA": "^CNXPHARMA",
    "NIFTY HEALTHCARE": "NIFTY_HEALTHCARE.NS",
    "NIFTY REALTY": "^CNXREALTY",
    "NIFTY CONSR DURBL": "NIFTY_CONSR_DURBL.NS",
    "NIFTY OIL AND GAS": "NIFTY_OIL_AND_GAS.NS",
    "NIFTY CHEMICALS": "NIFTY_CHEMICALS.NS",
    "NIFTY ENERGY": "^CNXENERGY",
    "NIFTY INFRA": "^CNXINFRA",
    "NIFTY COMMODITIES": "^CNXCMDT",
    "NIFTY CPSE": "NIFTY_CPSE.NS",
    "NIFTY PSE": "^CNXPSE",
    "NIFTY CONSUMPTION": "^CNXCONSUM",
    "NIFTY IND DEFENCE": "NIFTY_IND_DEFENCE.NS",
    "NIFTY CAPITAL MKT": "NIFTY_CAPITAL_MKT.NS",
    "NIFTY MNC": "^CNXMNC",
    "NIFTY INDIA MFG": "NIFTY_INDIA_MFG.NS",
}

GROUP_ORDER = ["Broad Market", "Sectoral", "Thematic"]

ACRONYMS = {
    "IT", "PSU", "FMCG", "MNC", "CPSE", "PSE", "ESG", "EV", "IPO", "SME", "USD", "FPI",
    "MAATR", "TR", "PR", "BSE", "MQVLV", "AQL", "AQLV", "MQ", "EW", "G-SEC",
}

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


def nice_index_name(raw: str) -> str:
    """'NIFTY INDIA CONSUMPTION' -> 'Nifty India Consumption' (keeps acronyms)."""

    def word(w: str) -> str:
        if not w:
            return w
        if "-" in w and w.upper() not in ACRONYMS:
            return "-".join(word(p) for p in w.split("-"))
        up = w.upper()
        if up in ACRONYMS:
            return up
        if up == "REITS":
            return "REITs"
        if up.startswith("NIFTY") and len(up) > 5:
            return "Nifty" + up[5:]
        m = re.fullmatch(r"([A-Za-z]+)(\d+)", w)
        if m:
            return m.group(1).capitalize() + m.group(2)
        if any(ch.isdigit() for ch in w) or not w.isalpha():
            return w
        return w.capitalize()

    return " ".join(word(w) for w in raw.split(" "))


def parse_nse_date(s: str | None) -> str | None:
    if not s:
        return None
    for fmt in ("%d-%b-%Y %H:%M", "%d-%b-%Y %H:%M:%S", "%d-%b-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def fetch_nse_all_indices() -> dict | None:
    """Official NSE snapshot of every index. Returns None if blocked/unavailable."""
    try:
        import requests
    except ImportError:
        print("WARN: requests not installed; skipping NSE source")
        return None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/market-data/live-market-indices",
    }
    s = requests.Session()
    s.headers.update(headers)
    for attempt in range(3):
        try:
            if attempt:
                s.get("https://www.nseindia.com/", timeout=15)  # cookie warm-up
            r = s.get(NSE_ALL_INDICES_URL, timeout=20)
            if r.status_code != 200:
                print(f"WARN: NSE allIndices HTTP {r.status_code} (attempt {attempt + 1})")
                time.sleep(2)
                continue
            data = r.json()
            rows = data.get("data") or []
            if len(rows) < 20:
                print(f"WARN: NSE allIndices returned only {len(rows)} rows")
                continue
            return data
        except Exception as e:  # noqa: BLE001
            print(f"WARN: NSE allIndices attempt {attempt + 1}: {e}")
            time.sleep(2)
    return None


def num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def yahoo_close_on_or_before(symbol: str, ref_date: str) -> float | None:
    """Close on the last session on/before ref_date (YYYY-MM-DD) from Yahoo history."""
    try:
        h = yf.Ticker(symbol).history(period="2mo", auto_adjust=True)
    except Exception as e:  # noqa: BLE001
        print(f"WARN: history {symbol}: {e}")
        return None
    if h is None or h.empty or len(h) < 3:
        return None
    closes = h["Close"].dropna()
    picked = None
    for ts, val in closes.items():
        if ts.strftime("%Y-%m-%d") <= ref_date:
            picked = float(val)
    return picked


def yahoo_daily(symbol: str) -> dict | None:
    """Last print + previous close from Yahoo fast_info."""
    try:
        fi = yf.Ticker(symbol).fast_info
        last = num(getattr(fi, "last_price", None))
        prev = num(getattr(fi, "previous_close", None))
    except Exception as e:  # noqa: BLE001
        print(f"WARN: fast_info {symbol}: {e}")
        return None
    if last is None:
        return None
    return {"last": round(last, 2), "prev": prev, "dailyPct": pct(last, prev)}


def yahoo_row(symbol: str, week_ref: str) -> dict | None:
    d = yahoo_daily(symbol)
    if not d or d["dailyPct"] is None:
        return None
    wk_close = yahoo_close_on_or_before(symbol, week_ref)
    return {
        "last": d["last"],
        "dailyPct": d["dailyPct"],
        "weeklyPct": pct(d["last"], wk_close) if wk_close else None,
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


def spread(a, b) -> float | None:
    if a is None or b is None:
        return None
    return round(a - b, 2)


def build_index_universe(as_of: str) -> dict | None:
    """Nifty 50 benchmark + curated MAJOR_INDICES (+ BSE) with daily/weekly returns."""
    nse = fetch_nse_all_indices()
    rows: list[dict] = []
    skipped: list[dict] = []
    not_tracked: list[str] = []
    benchmark = None
    data_date = as_of
    week_ref = None
    wanted = {sym: (name, group) for sym, name, group in MAJOR_INDICES}

    if nse:
        data_date = parse_nse_date(nse.get("timestamp")) or as_of
        week_ref = parse_nse_date((nse.get("dates") or {}).get("oneWeekAgo"))
        by_sym: dict[str, dict] = {}
        for x in nse["data"]:
            sym = (x.get("indexSymbol") or x.get("index") or "").strip()
            if sym and sym not in by_sym:
                by_sym[sym] = x
        for sym, x in by_sym.items():
            if sym != BENCHMARK_NSE and sym not in wanted:
                not_tracked.append(sym)
        for sym in [BENCHMARK_NSE] + list(wanted):
            x = by_sym.get(sym)
            if not x:
                skipped.append({"nseSymbol": sym, "reason": "not in NSE feed"})
                continue
            last = num(x.get("last"))
            daily = num(x.get("percentChange"))
            wk = num(x.get("oneWeekAgoVal"))
            weekly = pct(last, wk) if last and wk else None
            if last is None or daily is None:
                skipped.append({"nseSymbol": sym, "reason": "no data from NSE"})
                continue
            if sym == BENCHMARK_NSE:
                benchmark = {
                    "name": "Nifty 50",
                    "symbol": "^NSEI",
                    "nseSymbol": sym,
                    "last": round(last, 2),
                    "dailyPct": round(daily, 2),
                    "weeklyPct": weekly,
                    "source": "official",
                    "dataSource": "nse",
                }
                continue
            name, group = wanted[sym]
            rows.append(
                {
                    "id": sym,
                    "name": name,
                    "nseSymbol": sym,
                    "yahooSymbol": YAHOO_SYMBOLS.get(sym),
                    "group": group,
                    "dataSource": "nse",
                    "last": round(last, 2),
                    "dailyPct": round(daily, 2),
                    "weeklyPct": weekly,
                }
            )
        print(
            f"NSE allIndices: {len(rows)} major indices (+Nifty 50); "
            f"{len(not_tracked)} other NSE indices not tracked"
        )
    else:
        print("WARN: NSE unavailable — falling back to Yahoo Finance symbols")

    if not week_ref:
        d = datetime.strptime(data_date, "%Y-%m-%d").date()
        week_ref = (d - timedelta(days=7)).strftime("%Y-%m-%d")

    if benchmark is None:
        b = yahoo_row("^NSEI", week_ref)
        if not b:
            print("WARN: Nifty 50 unavailable from NSE and Yahoo")
            return None
        benchmark = {
            "name": "Nifty 50",
            "symbol": "^NSEI",
            "nseSymbol": BENCHMARK_NSE,
            **b,
            "source": "official",
            "dataSource": "yahoo",
        }

    if not nse:
        for sym, (name, group) in wanted.items():
            ysym = YAHOO_SYMBOLS.get(sym)
            if not ysym:
                skipped.append({"nseSymbol": sym, "reason": "no Yahoo symbol (NSE feed unavailable)"})
                continue
            r = yahoo_row(ysym, week_ref)
            time.sleep(0.2)
            if not r:
                skipped.append({"nseSymbol": sym, "yahooSymbol": ysym, "reason": "Yahoo returned no data"})
                continue
            rows.append(
                {
                    "id": sym,
                    "name": name,
                    "nseSymbol": sym,
                    "yahooSymbol": ysym,
                    "group": group,
                    "dataSource": "yahoo",
                    **r,
                }
            )

    for b in BSE_INDICES:
        r = yahoo_row(b["symbol"], week_ref)
        if not r:
            skipped.append({"yahooSymbol": b["symbol"], "reason": "Yahoo returned no data"})
            continue
        rows.append(
            {
                "id": b["symbol"],
                "name": b["name"],
                "nseSymbol": None,
                "yahooSymbol": b["symbol"],
                "group": b.get("group", "Broad Market"),
                "dataSource": "yahoo",
                **r,
            }
        )

    for r in rows:
        r["isBenchmark"] = False
        r["vsNiftyDaily"] = spread(r["dailyPct"], benchmark["dailyPct"])
        r["vsNiftyWeekly"] = spread(r["weeklyPct"], benchmark["weeklyPct"])

    # Nifty 50 as a visible row (spread 0) so the ranked list splits on it
    rows.append(
        {
            "id": BENCHMARK_NSE,
            "name": "Nifty 50",
            "nseSymbol": BENCHMARK_NSE,
            "yahooSymbol": "^NSEI",
            "group": "Broad Market",
            "dataSource": benchmark["dataSource"],
            "last": benchmark["last"],
            "dailyPct": benchmark["dailyPct"],
            "weeklyPct": benchmark["weeklyPct"],
            "isBenchmark": True,
            "vsNiftyDaily": 0.0 if benchmark["dailyPct"] is not None else None,
            "vsNiftyWeekly": 0.0 if benchmark["weeklyPct"] is not None else None,
        }
    )

    rows.sort(key=lambda r: (GROUP_ORDER.index(r["group"]) if r["group"] in GROUP_ORDER else 99, r["name"]))
    return {
        "benchmark": benchmark,
        "indices": rows,
        "skipped": skipped,
        "notTracked": sorted(not_tracked),
        "dataDate": data_date,
        "weekRefDate": week_ref,
        "primarySource": "nse" if nse else "yahoo",
    }


def build_indices(watchlist: list[dict], as_of: str) -> dict | None:
    uni = build_index_universe(as_of)
    if not uni:
        return None
    benchmark = uni["benchmark"]
    by_nse = {
        r["nseSymbol"]: r for r in uni["indices"] if r.get("nseSymbol") and not r.get("isBenchmark")
    }

    by_sector: dict[str, list] = {}
    for s in watchlist:
        by_sector.setdefault(s.get("sector") or "Other", []).append(s)

    mapping = {m["sector"]: m for m in SECTOR_INDEX_MAP}
    sectors_out = []
    links: dict[str, dict] = {}
    for sec, names in by_sector.items():
        tickers = [s["ticker"] for s in names]
        m = mapping.get(sec) or {}
        off = by_nse.get(m.get("nseSymbol")) if m.get("nseSymbol") else None
        wl = watchlist_sector_returns(names)
        notes: list[str] = []

        daily, daily_src = wl["dailyPct"], "watchlist"
        weekly, weekly_src = wl["weeklyPct"], "watchlist"
        if off and off.get("dailyPct") is not None:
            daily, daily_src = off["dailyPct"], "official"
        if off and off.get("weeklyPct") is not None:
            weekly, weekly_src = off["weeklyPct"], "official"

        if daily_src == "watchlist" and weekly_src == "watchlist":
            notes.append("Watchlist sector vs Nifty (not official index)")
            source = "watchlist"
        elif daily_src == "official" and weekly_src == "official":
            source = "official"
        else:
            source = "mixed"
            if daily_src == "watchlist":
                notes.append("Daily: watchlist equal-weight (official data missing)")
            if weekly_src == "watchlist":
                notes.append("Weekly: watchlist equal-weight (official history missing)")
        if off and m.get("note"):
            notes.append(m["note"])

        if off:
            link = links.setdefault(off["nseSymbol"], {"sectors": [], "tickers": []})
            link["sectors"].append(sec)
            link["tickers"].extend(tickers)

        sectors_out.append(
            {
                "sector": sec,
                "indexName": off["name"] if off else None,
                "symbol": (off.get("yahooSymbol") or off["nseSymbol"]) if off else None,
                "nseSymbol": off["nseSymbol"] if off else None,
                "source": source,
                "dailySource": daily_src,
                "weeklySource": weekly_src,
                "last": off["last"] if off else None,
                "dailyPct": daily,
                "weeklyPct": weekly,
                "vsNiftyDaily": spread(daily, benchmark["dailyPct"]),
                "vsNiftyWeekly": spread(weekly, benchmark["weeklyPct"]),
                "watchlistTickers": tickers,
                "watchlistCount": len(tickers),
                "note": "; ".join(notes) if notes else None,
            }
        )

    for r in uni["indices"]:
        link = links.get(r.get("nseSymbol") or "")
        r["watchlistSectors"] = link["sectors"] if link else []
        r["watchlistTickers"] = link["tickers"] if link else []

    groups = []
    for g in GROUP_ORDER:
        n = sum(1 for r in uni["indices"] if r["group"] == g)
        if n:
            groups.append({"group": g, "count": n})

    src_txt = (
        "NSE allIndices (official)" if uni["primarySource"] == "nse" else "Yahoo Finance (NSE unavailable)"
    )
    return {
        "asOf": uni["dataDate"],
        "timezone": "Asia/Kolkata",
        "lastRunUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "primarySource": uni["primarySource"],
        "weekRefDate": uni["weekRefDate"],
        "weeklyBasis": f"Close vs close on {uni['weekRefDate']} (1 calendar week)",
        "benchmark": benchmark,
        "groups": groups,
        "indices": uni["indices"],
        "sectors": sectors_out,
        "skipped": uni["skipped"],
        "notTracked": uni["notTracked"],
        "disclaimer": (
            "Research / personal tracking only — not investment advice. "
            f"Index levels from {src_txt}; BSE Sensex via Yahoo Finance. "
            "Watchlist sectors fall back to equal-weight watchlist average when no official index."
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
        print(
            f"Updated indices.json ({len(indices['indices'])} indices, "
            f"{len(indices['sectors'])} watchlist sectors vs Nifty 50, source={indices['primarySource']})"
        )
    else:
        print("WARN: skipped indices.json refresh")

    sync_docs_data()

    print(f"Updated {updated}/{len(watchlist)} tickers for {day}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
