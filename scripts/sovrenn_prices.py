"""Price / buy-zone refresh for public/data/sovrenn.json (used by
sovrenn_ingest.py and daily_update.py). Real Yahoo Finance data only; any
value that cannot be fetched is stored as null (shown as n/a).

Buy-zone rule (daily chart, same as watchlist): all of
  * close above 200 DMA
  * near 20 or 50 DMA support: close within 0% to +4% of the 20 DMA or 50 DMA
  * RSI(14) between 40 and 60
  * not extended: close no more than 8% above the 20 DMA
"""
from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf

IST = ZoneInfo("Asia/Kolkata")

# Manually verified Yahoo symbols where the Sovrenn code does not resolve
# (key = sovrenn.json "key"). Name checked against Yahoo longName.
OVERRIDES = {
    "544161": ["DPABHUSHAN.NS"],  # D. P. Abhushan Limited
    "PARTH": ["PARTH-SM.NS"],  # Parth Electricals & Engineering Limited (NSE-SME)
    "ANAWIL": ["ANAWIL-SM.NS"],  # Anawil Wire & Engineering Limited (NSE-SME)
    "538920": ["VINCOFE.NS"],  # Vintage Coffee & Beverages Limited (BSE 538920)
    "530475": ["TINNARUBR.NS"],  # Tinna Rubber & Infrastructure Limited (BSE 530475)
}


def _rsi(closes):
    if len(closes) < 15:
        return None
    d = closes.diff().dropna()
    g = d.clip(lower=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = g / l.replace(0, math.nan)
    v = float((100 - 100 / (1 + rs)).iloc[-1])
    return None if math.isnan(v) else round(v, 1)


def _hist(t):
    try:
        h = yf.Ticker(t).history(period="2y", auto_adjust=False)
        if h is None or h.empty:
            return None
        h = h[h["Close"].notna()]
        return h if len(h) else None
    except Exception as e:  # noqa: BLE001
        print(f"WARN sovrenn: {t}: {e}")
        return None


def _search(name: str) -> list[str]:
    try:
        q = name.replace("LIMITED", "").replace("LTD", "").strip()
        res = yf.Search(q, max_results=8).quotes
        return [r["symbol"] for r in res if str(r.get("symbol", "")).endswith((".NS", ".BO"))]
    except Exception:  # noqa: BLE001
        return []


def _mcap(t):
    try:
        v = yf.Ticker(t).fast_info.get("marketCap")
        return round(float(v) / 1e7) if v else None  # INR crore
    except Exception:  # noqa: BLE001
        return None


def evaluate(h) -> dict:
    c = h["Close"]
    last = float(c.iloc[-1])
    d20 = float(c.tail(20).mean()) if len(c) >= 20 else None
    d50 = float(c.tail(50).mean()) if len(c) >= 50 else None
    d200 = float(c.tail(200).mean()) if len(c) >= 200 else None
    rsi = _rsi(c)
    near = lambda d: d is not None and 0 <= (last / d - 1) * 100 <= 4  # noqa: E731
    checks = {
        "above200": None if d200 is None else last > d200,
        "nearSupport": None if d20 is None else (near(d20) or near(d50)),
        "rsiOk": None if rsi is None else 40 <= rsi <= 60,
        "notExtended": None if d20 is None else (last / d20 - 1) * 100 <= 8,
    }
    if any(v is None for v in checks.values()):
        flag, why = "n/a", "insufficient history (" + ", ".join(k for k, v in checks.items() if v is None) + ")"
    else:
        flag = "Y" if all(checks.values()) else "N"
        why = "all rules met" if flag == "Y" else "fails: " + ", ".join(k for k, v in checks.items() if not v)
    r = lambda x: None if x is None else round(x, 2)  # noqa: E731
    return {"price": r(last), "priceDate": c.index[-1].strftime("%Y-%m-%d"), "dma20": r(d20), "dma50": r(d50),
            "dma200": r(d200), "rsi14": rsi, "buyZone": flag, "buyZoneNote": why, "bars": len(c)}


def refresh(db: list[dict]) -> None:
    for e in db:
        cands = ([e["ticker"]] if e.get("ticker") else []) + [t for t in e.get("candidates", []) if t != e.get("ticker")]
        cands += [t for t in OVERRIDES.get(e["key"], []) if t not in cands]
        h, used = None, None
        for t in cands:
            x = _hist(t)
            if x is not None and (h is None or len(x) > len(h)):
                h, used = x, t
            if h is not None and len(h) >= 20:
                break
        if h is None or len(h) < 20:
            for t in _search(e.get("nameRaw") or e["name"]):
                x = _hist(t)
                if x is not None and (h is None or len(x) > len(h)):
                    h, used = x, t
                    e["tickerResolvedBy"] = "yahoo search"
                if h is not None and len(h) >= 20:
                    break
        if h is None:
            print(f"WARN sovrenn: no data for {e['key']} ({cands})")
            e.update({"ticker": e.get("ticker"), "price": None, "buyZone": "n/a", "buyZoneNote": "no price data"})
            continue
        e["ticker"] = used
        ev = evaluate(h)
        if len(h) < 20:
            ev["buyZoneNote"] = "Yahoo has no daily history for this listing (latest quote only)"
        e.update(ev)
        # close on the first-highlight date (edition goes out after market close)
        idx = [i for i, d in enumerate(h.index.strftime("%Y-%m-%d")) if d <= e["firstHighlighted"]]
        if idx:
            e["priceAtHighlight"] = round(float(h["Close"].iloc[idx[-1]]), 2)
            e["priceAtHighlightDate"] = h.index[idx[-1]].strftime("%Y-%m-%d")
        else:
            e["priceAtHighlight"] = None
            e["priceAtHighlightDate"] = None
        p0 = e.get("priceAtHighlight")
        e["pctSinceHighlight"] = round((ev["price"] / p0 - 1) * 100, 2) if p0 else None
        m = _mcap(used)
        e["mcapCr"] = m
        e["lastUpdated"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
        print(f"sovrenn {used}: {ev['price']} bz={ev['buyZone']} since={e['pctSinceHighlight']}")
