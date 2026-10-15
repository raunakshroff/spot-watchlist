#!/usr/bin/env python3
"""Compute custom equal-weight baskets and merge into indices / history / constituents.

Definitions live in public/data/custom_baskets.json. First batch: Chemicals macro gaps.
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import yfinance as yf
except ImportError as e:  # pragma: no cover
    raise SystemExit("yfinance required") from e

import pandas as pd

IST = ZoneInfo("Asia/Kolkata")
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public" / "data"
ADV_FLOOR = 1e7  # ₹1 crore
HORIZON_DAYS = {"m1": 30, "m3": 91, "m6": 182, "y1": 365, "y5": 365 * 5}


def load_json(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def save_json(name: str, obj, *, compact: bool = False) -> None:
    path = DATA / name
    if compact:
        path.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def pct(a, b):
    if a is None or b is None or not b:
        return None
    return round((a / b - 1.0) * 100, 2)


def spread(a, b):
    if a is None or b is None:
        return None
    return round(a - b, 2)


def fetch_histories(symbols: list[str], years: int = 5) -> dict[str, pd.DataFrame]:
    """symbol -> DataFrame with Close, Volume indexed by date."""
    out: dict[str, pd.DataFrame] = {}
    tickers = [f"{s}.NS" for s in symbols]
    for i in range(0, len(tickers), 40):
        chunk = tickers[i : i + 40]
        try:
            df = yf.download(
                chunk,
                period=f"{years}y",
                group_by="ticker",
                threads=True,
                progress=False,
                auto_adjust=True,
            )
        except Exception as e:  # noqa: BLE001
            print(f"WARN: download chunk {i}: {e}")
            time.sleep(1)
            continue
        for t in chunk:
            sym = t[: -len(".NS")]
            try:
                if isinstance(df.columns, pd.MultiIndex):
                    if t not in df.columns.get_level_values(0):
                        continue
                    sub = df[t][["Close", "Volume"]].dropna(subset=["Close"])
                else:
                    sub = df[["Close", "Volume"]].dropna(subset=["Close"])
                if len(sub) >= 25:
                    sub = sub.copy()
                    sub.index = pd.to_datetime(sub.index).tz_localize(None)
                    out[sym] = sub
            except Exception:
                continue
        time.sleep(0.15)
    return out


def adv_inr(hist: pd.DataFrame, window: int = 20) -> float | None:
    if hist is None or len(hist) < window:
        return None
    tail = hist.tail(window)
    traded = (tail["Close"] * tail["Volume"]).mean()
    if traded != traded:
        return None
    return float(traded)


def filter_members(candidates: list[dict], hist: dict[str, pd.DataFrame], min_members: int):
    kept, excluded = [], []
    for c in candidates:
        sym = c["symbol"]
        h = hist.get(sym)
        if h is None or len(h) < 30:
            excluded.append({**c, "reason": "history"})
            continue
        adv = adv_inr(h)
        if adv is None or adv < ADV_FLOOR:
            excluded.append({**c, "reason": "liquidity", "adv": None if adv is None else round(adv)})
            continue
        kept.append({**c, "adv": round(adv)})
    status = "ok"
    skip = None
    if len(kept) < min_members:
        status = "skipped"
        skip = f"only {len(kept)} liquid names (min {min_members})"
    return kept, excluded, status, skip


def member_return(hist: pd.DataFrame, calendar_days: int, as_of: pd.Timestamp) -> float | None:
    if hist is None or hist.empty:
        return None
    target = as_of - timedelta(days=calendar_days)
    closes = hist["Close"]
    # last on/before as_of and on/before target
    last = closes[closes.index <= as_of]
    past = closes[closes.index <= target]
    if last.empty or past.empty:
        return None
    return pct(float(last.iloc[-1]), float(past.iloc[-1]))


def ew_series(members: list[str], hist: dict[str, pd.DataFrame], start: pd.Timestamp, end: pd.Timestamp):
    """Chain daily equal-weight returns into a level series rebased to 100."""
    # Align on union of dates
    frames = []
    for s in members:
        h = hist.get(s)
        if h is None:
            continue
        frames.append(h["Close"].rename(s))
    if not frames:
        return [], []
    px = pd.concat(frames, axis=1).sort_index()
    px = px.loc[(px.index >= start) & (px.index <= end)]
    # require at least 3 names that day
    rets = px.pct_change()
    valid = rets.notna().sum(axis=1)
    ew = rets.mean(axis=1, skipna=True)
    ew = ew.where(valid >= min(3, len(members)))
    level = (1 + ew.fillna(0)).cumprod() * 100
    # null out until first valid
    first = ew.first_valid_index()
    if first is not None:
        level.loc[level.index < first] = math.nan
    dates = [d.strftime("%Y-%m-%d") for d in level.index]
    vals = [None if (v != v) else round(float(v), 2) for v in level.tolist()]
    return dates, vals


def nifty_hist() -> pd.DataFrame | None:
    try:
        h = yf.Ticker("^NSEI").history(period="5y", auto_adjust=True)
    except Exception as e:  # noqa: BLE001
        print(f"WARN: Nifty history: {e}")
        return None
    if h is None or h.empty:
        return None
    h = h[["Close", "Volume"]].dropna(subset=["Close"]).copy()
    h.index = pd.to_datetime(h.index).tz_localize(None)
    return h


def build_and_merge(*, years: int = 5) -> dict:
    defs = load_json("custom_baskets.json")
    indices_doc = load_json("indices.json")
    as_of = pd.Timestamp(indices_doc["asOf"])
    bench = indices_doc["benchmark"]

    # gather all candidate symbols
    all_syms = sorted(
        {
            c["symbol"]
            for b in defs["baskets"]
            if not b.get("skipReason")
            for c in b.get("candidates") or []
        }
    )
    print(f"Downloading history for {len(all_syms)} candidate symbols…")
    hist = fetch_histories(all_syms, years=years)
    print(f"  got history for {len(hist)}")
    nh = nifty_hist()

    # Nifty horizon returns from indices_doc when present
    def bench_ret(key):
        if key == "daily":
            return bench.get("dailyPct")
        if key == "weekly":
            return bench.get("weeklyPct")
        return bench.get(f"{key}Pct")

    custom_rows = []
    const_blocks = []
    series_daily: dict[str, dict] = {}
    report = {"built": [], "skipped": [], "excluded": {}}

    for b in defs["baskets"]:
        iid = b["id"]
        if b.get("skipReason"):
            report["skipped"].append({"id": iid, "reason": b["skipReason"], "candidates": len(b.get("candidates") or [])})
            continue
        kept, excluded, status, skip = filter_members(b["candidates"], hist, b.get("minMembers") or 5)
        report["excluded"][iid] = excluded
        if status != "ok":
            report["skipped"].append({"id": iid, "reason": skip, "kept": len(kept), "excluded": len(excluded)})
            # still record empty constituents block
            const_blocks.append(
                {
                    "id": iid,
                    "status": "n/a",
                    "reason": skip,
                    "count": 0,
                    "members": [],
                    "csv": None,
                    "membershipAsOf": as_of.strftime("%Y-%m-%d"),
                }
            )
            continue

        # returns
        daily_rets = []
        for m in kept:
            h = hist[m["symbol"]]
            closes = h["Close"]
            if len(closes) >= 2:
                daily_rets.append(pct(float(closes.iloc[-1]), float(closes.iloc[-2])))
        daily = None if not daily_rets else round(sum(x for x in daily_rets if x is not None) / len(daily_rets), 2)

        weekly_rets = [member_return(hist[m["symbol"]], 7, as_of) for m in kept]
        weekly_rets = [x for x in weekly_rets if x is not None]
        weekly = None if not weekly_rets else round(sum(weekly_rets) / len(weekly_rets), 2)

        horizons = {}
        for key, days in HORIZON_DAYS.items():
            rs = [member_return(hist[m["symbol"]], days, as_of) for m in kept]
            rs = [x for x in rs if x is not None]
            horizons[key] = None if not rs else round(sum(rs) / len(rs), 2)

        last_vals = [float(hist[m["symbol"]]["Close"].iloc[-1]) for m in kept]
        last = round(sum(last_vals) / len(last_vals), 2) if last_vals else None

        row = {
            "id": iid,
            "name": b["name"],
            "nseSymbol": None,
            "yahooSymbol": None,
            "group": f"Custom: {b['macro']}",
            "dataSource": "custom",
            "last": last,
            "dailyPct": daily,
            "weeklyPct": weekly,
            "m1Pct": horizons["m1"],
            "m3Pct": horizons["m3"],
            "m6Pct": horizons["m6"],
            "y1Pct": horizons["y1"],
            "y5Pct": horizons["y5"],
            "isBenchmark": False,
            "vsNiftyDaily": spread(daily, bench_ret("daily")),
            "vsNiftyWeekly": spread(weekly, bench_ret("weekly")),
            "vsNiftyM1": spread(horizons["m1"], bench_ret("m1")),
            "vsNiftyM3": spread(horizons["m3"], bench_ret("m3")),
            "vsNiftyM6": spread(horizons["m6"], bench_ret("m6")),
            "vsNiftyY1": spread(horizons["y1"], bench_ret("y1")),
            "vsNiftyY5": spread(horizons["y5"], bench_ret("y5")),
            "watchlistSectors": [],
            "watchlistTickers": [],
            "custom": {
                "macro": b["macro"],
                "kind": b.get("kind"),
                "method": "equal-weight · liquid ≥₹1cr ADV · screener universe",
                "memberCount": len(kept),
            },
        }
        custom_rows.append(row)

        # constituents for panel
        wl = {((s.get("ticker") or "").replace(".NS", "").upper()) for s in load_json("watchlist.json")}
        members = []
        for m in kept:
            h = hist[m["symbol"]]
            dret = None
            if len(h) >= 2:
                dret = pct(float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2]))
            members.append(
                {
                    "symbol": m["symbol"],
                    "name": m.get("name"),
                    "industry": b.get("screenerName") or b.get("niche"),
                    "weight": round(100.0 / len(kept), 2),
                    "dailyPct": dret,
                    "onWatchlist": m["symbol"].upper() in wl,
                }
            )
        const_blocks.append(
            {
                "id": iid,
                "status": "ok",
                "reason": None,
                "count": len(members),
                "members": members,
                "csv": None,
                "membershipAsOf": as_of.strftime("%Y-%m-%d"),
                "method": defs.get("method"),
            }
        )

        # chart series (~1Y daily)
        start = as_of - timedelta(days=400)
        dates, vals = ew_series([m["symbol"] for m in kept], hist, start, as_of)
        series_daily[iid] = {"dates": dates, "values": vals}

        report["built"].append({"id": iid, "members": len(kept), "excluded": len(excluded)})
        print(f"OK {iid}: {len(kept)} members, daily={daily}, y1={horizons['y1']}")

    # Merge into indices.json — replace prior custom rows for these macros
    existing = [r for r in indices_doc.get("indices") or [] if not str(r.get("group", "")).startswith("Custom:")]
    existing.extend(custom_rows)
    # group order
    groups = []
    order = ["Broad Market", "Sectoral", "Thematic", "Strategy", "BSE"]
    customs = sorted({r["group"] for r in custom_rows})
    for g in order + customs:
        n = sum(1 for r in existing if r["group"] == g)
        if n:
            groups.append({"group": g, "count": n})
    indices_doc["indices"] = existing
    indices_doc["groups"] = groups
    indices_doc["customNote"] = (
        "Custom: * baskets are equal-weight liquid screens from screener.in basic industries "
        "(and curated micro-niches). Not official NSE/BSE indices. Research only."
    )
    save_json("indices.json", indices_doc)

    # Merge constituents
    if (DATA / "index_constituents.json").exists():
        cdoc = load_json("index_constituents.json")
    else:
        cdoc = {"indices": [], "counts": {}}
    keep = [x for x in cdoc.get("indices") or [] if not str(x.get("id", "")).startswith("CUSTOM-")]
    keep.extend(const_blocks)
    cdoc["indices"] = keep
    with_c = sum(1 for x in keep if x.get("status") == "ok")
    cdoc["counts"] = {"withConstituents": with_c, "withoutConstituents": len(keep) - with_c, "total": len(keep)}
    cdoc["asOf"] = as_of.strftime("%Y-%m-%d")
    save_json("index_constituents.json", cdoc, compact=True)

    # Merge history daily series for customs
    if (DATA / "index_history.json").exists():
        hdoc = load_json("index_history.json")
    else:
        hdoc = {
            "asOf": as_of.strftime("%Y-%m-%d"),
            "timezone": "Asia/Kolkata",
            "benchmarkId": "NIFTY 50",
            "daily": {"dates": [], "series": {}},
            "weekly": {"dates": [], "series": {}},
            "coverage": {},
        }
    # Use Nifty daily dates as spine when possible
    spine = hdoc.get("daily", {}).get("dates") or []
    for iid, pack in series_daily.items():
        by_d = dict(zip(pack["dates"], pack["values"]))
        if spine:
            hdoc["daily"]["series"][iid] = [by_d.get(d) for d in spine]
        else:
            hdoc["daily"]["dates"] = pack["dates"]
            hdoc["daily"]["series"][iid] = pack["values"]
        hdoc.setdefault("coverage", {})[iid] = {
            "dailyBars": sum(1 for v in hdoc["daily"]["series"][iid] if v is not None),
            "weeklyBars": 0,
            "firstDaily": next((d for d, v in zip(hdoc["daily"]["dates"], hdoc["daily"]["series"][iid]) if v is not None), None),
            "firstWeekly": None,
        }
    save_json("index_history.json", hdoc, compact=True)

    # Persist exclusion report onto definitions
    defs["lastBuild"] = {
        "asOf": as_of.strftime("%Y-%m-%d"),
        "builtUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "report": report,
    }
    save_json("custom_baskets.json", defs)

    print(f"Built {len(report['built'])} baskets, skipped {len(report['skipped'])}")
    return report


if __name__ == "__main__":
    rep = build_and_merge()
    docs = ROOT / "docs" / "data"
    if docs.is_dir():
        for name in ("indices.json", "index_constituents.json", "index_history.json", "custom_baskets.json"):
            src = DATA / name
            if src.exists():
                (docs / name).write_bytes(src.read_bytes())
        print("Synced docs/data/")
