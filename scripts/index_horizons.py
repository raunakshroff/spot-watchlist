#!/usr/bin/env python3
"""Multi-horizon returns + compact chart history for Spot Watchlist indices.

Primary source: NSE archives ind_close_all_DDMMYYYY.csv (official closes for
nearly every NSE index). Yahoo Finance for BSE Sensex / BSE 100 / BSE 500 and
as a fallback when an archive date is missing.

Writes / updates:
  - horizon fields on each indices.json row (m1/m3/m6/y1/y5 + vs Nifty)
  - public/data/index_history.json (daily ~1Y + weekly ~5Y closes)
"""

from __future__ import annotations

import csv
import io
import json
import math
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None  # type: ignore

IST = ZoneInfo("Asia/Kolkata")
ARCHIVE_URL = "https://archives.nseindia.com/content/indices/ind_close_all_{ddmmyyyy}.csv"

# calendar lookbacks for horizon returns
HORIZON_DAYS = {
    "m1": 30,
    "m3": 91,
    "m6": 182,
    "y1": 365,
    "y5": 365 * 5,
}

HORIZON_KEYS = ("m1", "m3", "m6", "y1", "y5")

# Archive "Index Name" overrides when fuzzy match would fail
ARCHIVE_NAME_OVERRIDES: dict[str, str] = {
    "NIFTY 50": "Nifty 50",
    "NIFTY NEXT 50": "Nifty Next 50",
    "NIFTY MIDCAP 100": "NIFTY Midcap 100",
    "NIFTY SMLCAP 100": "NIFTY Smallcap 100",
    "NIFTY SMLCAP 250": "Nifty Smallcap 250",
    "NIFTY SMLCAP 50": "Nifty Smallcap 50",
    "NIFTY MIDCAP 150": "Nifty Midcap 150",
    "NIFTY MIDCAP 50": "Nifty Midcap 50",
    "NIFTY FIN SERVICE": "Nifty Financial Services",
    "NIFTY PVT BANK": "Nifty Private Bank",
    "NIFTY CONSR DURBL": "Nifty Consumer Durables",
    "NIFTY OIL AND GAS": "Nifty Oil & Gas",
    "NIFTY HEALTHCARE": "Nifty Healthcare Index",
    "NIFTY IND DEFENCE": "Nifty India Defence",
    "NIFTY IND DIGITAL": "Nifty India Digital",
    "NIFTY IND TOURISM": "Nifty India Tourism",
    "NIFTY INDIA MFG": "Nifty India Manufacturing",
    "NIFTY CONSUMPTION": "Nifty India Consumption",
    "NIFTY NEW CONSUMP": "Nifty India New Age Consumption",
    "NIFTY INFRALOG": "Nifty India Infrastructure & Logistics",
    "NIFTY INTERNET": "Nifty India Internet",
    "NIFTY RAILWAYSPSU": "Nifty India Railways PSU",
    "NIFTY CORP MAATR": "Nifty India Select 5 Corporate Groups (MAATR)",
    "NIFTY TATA 25 CAP": "Nifty India Corporate Group Index - Tata Group 25% Cap",
    "NIFTY EV": "Nifty EV & New Age Automotive",
    "NIFTYCONGLOMERATE": "Nifty Conglomerate 50",
    "NIFTY REITS REALTY": "Nifty REITs & Realty",
    "NIFTY MS FIN SERV": "Nifty Midsmall Financial Services",
    "NIFTY MIDSML HLTH": "Nifty Midsmall Healthcare",
    "NIFTY MS IT TELCM": "Nifty Midsmall IT & Telecom",
    "NIFTY MS IND CONS": "Nifty Midsmall India Consumption",
    "NIFTY FINSRV25 50": "Nifty Financial Services 25/50",
    "NIFTY FINSEREXBNK": "Nifty Financial Services Ex-Bank",
    "NIFTY500 HEALTH": "Nifty500 Healthcare",
    "NIFTY LARGEMID250": "Nifty LargeMidcap 250",
    "NIFTY MICROCAP250": "Nifty Microcap 250",
    "NIFTY MIDSML 400": "Nifty MidSmallcap 400",
    "NIFTY MIDSMALL 50 50": "Nifty MidSmallcap400 50:50",
    "NIFTY MID SELECT": "Nifty Midcap Select",
    "NIFTY TOTAL MKT": "Nifty Total Market",
    "NIFTY500 MULTICAP": "Nifty500 Multicap 50:25:25",
    "NIFTY500 LMS EQL": "Nifty500 LargeMidSmall Equal-Cap Weighted",
    "NIFTY FPI 150": "Nifty India FPI 150",
    "NIFTY SMALLCAP 500": "Nifty Smallcap 500",
    "NIFTY SERV SECTOR": "Nifty Services Sector",
    "NIFTY TRANS LOGIS": "Nifty Transportation & Logistics",
    "NIFTY DIV OPPS 50": "Nifty Dividend Opportunities 50",
    "NIFTY GROWSECT 15": "Nifty Growth Sectors 15",
    "NIFTY LOW VOL 50": "Nifty Low Volatility 50",
    "NIFTY HIGHBETA 50": "Nifty High Beta 50",
    "NIFTY ALPHA 50": "Nifty Alpha 50",
    "NIFTY ALPHALOWVOL": "Nifty Alpha Low-Volatility 30",
    "NIFTY AQL 30": "Nifty Alpha Quality Low-Volatility 30",
    "NIFTY AQLV 30": "Nifty Alpha Quality Value Low-Volatility 30",
    "NIFTY QLTY LV 30": "Nifty Quality Low-Volatility 30",
    "NIFTY100 EQL WGT": "Nifty100 Equal Weight",
    "NIFTY100 LIQ 15": "Nifty100 Liquid 15",
    "NIFTY100 LOWVOL30": "Nifty100 Low Volatility 30",
    "NIFTY100 QUALTY30": "Nifty100 Quality 30",
    "NIFTY100 ESG": "Nifty100 ESG",
    "NIFTY100ESGSECLDR": "Nifty100 ESG Sector Leaders",
    "NIFTY100 ENH ESG": "Nifty100 Enhanced ESG",
    "NIFTY100 ALPHA 30": "Nifty100 Alpha 30",
    "NIFTY200 ALPHA 30": "Nifty200 Alpha 30",
    "NIFTY200MOMENTM30": "Nifty200 Momentum 30",
    "NIFTY200 QUALTY30": "Nifty200 Quality 30",
    "NIFTY200 VALUE 30": "Nifty200 Value 30",
    "NIFTY50 EQL WGT": "Nifty50 Equal Weight",
    "NIFTY50 VALUE 20": "Nifty50 Value 20",
    "NIFTY50 USD": "Nifty50 USD",
    "NIFTY50 SHARIAH": "Nifty50 Shariah",
    "NIFTY500 SHARIAH": "Nifty500 Shariah",
    "NIFTY SHARIAH 25": "Nifty Shariah 25",
    "NIFTY MID LIQ 15": "Nifty Midcap Liquid 15",
    "NIFTY M150 QLTY50": "Nifty Midcap150 Quality 50",
    "NIFTYM150MOMNTM50": "Nifty Midcap150 Momentum 50",
    "NIFTY SML250 Q50": "Nifty Smallcap250 Quality 50",
    "NIFTYSML250MQ 100": "Nifty Smallcap250 Momentum Quality 100",
    "NIFTYMS400 MQ 100": "Nifty MidSmallcap400 Momentum Quality 100",
    "NIFTY500MOMENTM50": "Nifty500 Momentum 50",
    "NIFTY500 QLTY50": "Nifty500 Quality 50",
    "NIFTY500 VALUE 50": "Nifty500 Value 50",
    "NIFTY500 LOWVOL50": "Nifty500 Low Volatility 50",
    "NIFTY500 EW": "Nifty500 Equal Weight",
    "NIFTY500 MQVLV50": "Nifty500 Multifactor MQVLV 50",
    "NIFTY500 FLEXICAP": "Nifty500 Flexicap Quality 30",
    "NIFTY MULTI MQ 50": "Nifty500 Multicap Momentum Quality 50",
    "NIFTY MULTI MFG": "Nifty500 Multicap India Manufacturing 50:30:20",
    "NIFTY MULTI INFRA": "Nifty500 Multicap Infrastructure 50:30:20",
    "NIFTY TMMQ 50": "Nifty Total Market Momentum Quality 50",
    "NIFTY TOP 10 EW": "Nifty Top 10 Equal Weight",
    "NIFTY TOP 15 EW": "Nifty Top 15 Equal Weight",
    "NIFTY TOP 20 EW": "Nifty Top 20 Equal Weight",
    "NIFTY COREHOUSING": "Nifty Core Housing",
    "NIFTY HOUSING": "Nifty Housing",
    "NIFTY IPO": "Nifty IPO",
    "NIFTY MOBILITY": "Nifty Mobility",
    "NIFTY NONCYC CONS": "Nifty Non-Cyclical Consumer",
    "NIFTY RURAL": "Nifty Rural",
    "NIFTY SME EMERGE": "Nifty SME Emerge",
    "NIFTY WAVES": "Nifty Waves",
    "NIFTY CAPITAL MKT": "Nifty Capital Markets",
    "NIFTY CHEMICALS": "Nifty Chemicals",
    "NIFTY CEMENT": "Nifty Cement",
}


def _num(x) -> float | None:
    try:
        if x is None or x == "" or x == "-":
            return None
        v = float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def pct(a, b) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return round((a / b - 1.0) * 100, 2)


def spread(a, b) -> float | None:
    if a is None or b is None:
        return None
    return round(a - b, 2)


def _session() -> "requests.Session":
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
            ),
            "Accept": "text/csv,*/*",
        }
    )
    return s


def _parse_archive_csv(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    if "Index Name" not in text[:100]:
        return out
    for row in csv.DictReader(io.StringIO(text)):
        name = (row.get("Index Name") or "").strip()
        close = _num(row.get("Closing Index Value"))
        if name and close is not None:
            out[name] = close
    return out


def fetch_archive_exact(d: date, session: "requests.Session", cache: dict) -> dict[str, float] | None:
    """Fetch a single calendar day's archive CSV. None on miss. Uses cache."""
    key = d.isoformat()
    if key in cache:
        return cache[key]
    url = ARCHIVE_URL.format(ddmmyyyy=d.strftime("%d%m%Y"))
    try:
        r = session.get(url, timeout=25)
    except Exception as e:  # noqa: BLE001
        print(f"WARN: archive {d}: {e}")
        cache[key] = None
        return None
    if r.status_code != 200:
        cache[key] = None
        return None
    out = _parse_archive_csv(r.text)
    if len(out) < 20:
        cache[key] = None
        return None
    cache[key] = out
    return out


def fetch_archive_on(
    d: date,
    session: "requests.Session | None" = None,
    cache: dict | None = None,
    walk: int = 12,
) -> tuple[date, dict[str, float]] | None:
    """Return (actual_date, {archive_index_name: close}) walking back up to `walk` calendar days."""
    if requests is None:
        return None
    s = session or _session()
    cache = cache if cache is not None else {}
    for i in range(walk):
        day = d - timedelta(days=i)
        closes = fetch_archive_exact(day, s, cache)
        if closes:
            return day, closes
        time.sleep(0.05)
    return None


def _norm(s: str) -> str:
    return "".join(ch for ch in s.upper() if ch.isalnum())


def build_archive_lookup(archive_names: list[str], indices: list[dict]) -> dict[str, str]:
    """Map our index id -> archive Index Name."""
    by_norm = {_norm(n): n for n in archive_names}
    lookup: dict[str, str] = {}
    for row in indices:
        iid = row["id"]
        nse = row.get("nseSymbol") or ""
        if not nse and row.get("group") == "BSE":
            continue
        candidates = []
        if nse in ARCHIVE_NAME_OVERRIDES:
            candidates.append(ARCHIVE_NAME_OVERRIDES[nse])
        if row.get("name"):
            candidates.append(row["name"])
        if nse:
            candidates.append(nse)
            candidates.append(nse.replace("NIFTY", "Nifty"))
        found = None
        for c in candidates:
            if c in archive_names:
                found = c
                break
            hit = by_norm.get(_norm(c))
            if hit:
                found = hit
                break
        if found:
            lookup[iid] = found
    return lookup


def yahoo_close_on_or_before(symbol: str, ref: date) -> float | None:
    if yf is None:
        return None
    try:
        h = yf.Ticker(symbol).history(
            start=(ref - timedelta(days=14)).isoformat(),
            end=(ref + timedelta(days=2)).isoformat(),
            auto_adjust=True,
        )
    except Exception as e:  # noqa: BLE001
        print(f"WARN: yahoo history {symbol}: {e}")
        return None
    if h is None or h.empty:
        return None
    picked = None
    for ts, val in h["Close"].dropna().items():
        if ts.date() <= ref:
            picked = float(val)
    return picked


def yahoo_history_series(symbol: str, years: int = 5) -> dict[str, float]:
    """YYYY-MM-DD -> close from Yahoo (empty if unavailable)."""
    if yf is None:
        return {}
    try:
        h = yf.Ticker(symbol).history(period=f"{years}y", auto_adjust=True)
    except Exception as e:  # noqa: BLE001
        print(f"WARN: yahoo series {symbol}: {e}")
        return {}
    if h is None or h.empty or len(h) < 10:
        return {}
    out: dict[str, float] = {}
    for ts, val in h["Close"].dropna().items():
        out[ts.strftime("%Y-%m-%d")] = round(float(val), 4)
    return out


def enrich_indices_horizons(indices_doc: dict) -> dict:
    """Add m1/m3/m6/y1/y5 returns + vs Nifty using NSE archive snapshots + Yahoo for BSE."""
    if requests is None:
        print("WARN: requests missing — skipping horizon enrichment")
        return indices_doc

    as_of = date.fromisoformat(indices_doc["asOf"])
    session = _session()
    latest = fetch_archive_on(as_of, session)
    if not latest:
        print("WARN: could not load NSE archive for as-of date — horizons skipped")
        return indices_doc
    latest_day, latest_closes = latest
    lookup = build_archive_lookup(list(latest_closes.keys()), indices_doc.get("indices") or [])
    print(f"Archive map: {len(lookup)} indices linked (as-of {latest_day})")

    snaps: dict[str, tuple[date, dict[str, float]]] = {"asof": (latest_day, latest_closes)}
    for key, days in HORIZON_DAYS.items():
        target = as_of - timedelta(days=days)
        got = fetch_archive_on(target, session)
        if got:
            snaps[key] = got
            print(f"  horizon {key}: archive {got[0]} (target {target})")
        else:
            print(f"  WARN: no archive for horizon {key} near {target}")
        time.sleep(0.15)

    bench_id = "NIFTY 50"
    bench_arch = lookup.get(bench_id, "Nifty 50")
    bench_last = indices_doc.get("benchmark", {}).get("last")
    if bench_last is None:
        bench_last = latest_closes.get(bench_arch)

    # BSE via Yahoo
    bse_syms = {
        "^BSESN": "^BSESN",
        "BSE-100.BO": "BSE-100.BO",
        "BSE-500.BO": "BSE-500.BO",
    }
    bse_horiz: dict[str, dict[str, float | None]] = {}
    for iid, ysym in bse_syms.items():
        row = next((r for r in indices_doc["indices"] if r["id"] == iid), None)
        last = row["last"] if row else None
        bse_horiz[iid] = {}
        for key, days in HORIZON_DAYS.items():
            target = as_of - timedelta(days=days)
            past = yahoo_close_on_or_before(ysym, target)
            bse_horiz[iid][key] = pct(last, past)
            time.sleep(0.05)

    bench_rets: dict[str, float | None] = {}
    for key in HORIZON_KEYS:
        past_map = snaps.get(key, (None, {}))[1]
        past = past_map.get(bench_arch)
        bench_rets[key] = pct(bench_last, past)

    # attach to benchmark object
    b = indices_doc.setdefault("benchmark", {})
    for key in HORIZON_KEYS:
        b[f"{key}Pct"] = bench_rets[key]

    missing_long: list[str] = []
    for row in indices_doc.get("indices") or []:
        iid = row["id"]
        last = row.get("last")
        for key in HORIZON_KEYS:
            field = f"{key}Pct"
            vs_field = f"vsNifty{key[0].upper()}{key[1:]}" if False else None
            # consistent field names: m1Pct / vsNiftyM1, y1Pct / vsNiftyY1, y5Pct / vsNiftyY5
            vs_name = {
                "m1": "vsNiftyM1",
                "m3": "vsNiftyM3",
                "m6": "vsNiftyM6",
                "y1": "vsNiftyY1",
                "y5": "vsNiftyY5",
            }[key]

            if iid in bse_horiz:
                ret = bse_horiz[iid].get(key)
            else:
                arch = lookup.get(iid)
                past_map = snaps.get(key, (None, {}))[1]
                past = past_map.get(arch) if arch else None
                ret = pct(last, past)
            row[field] = ret
            row[vs_name] = 0.0 if row.get("isBenchmark") and ret is not None else spread(ret, bench_rets.get(key))
            if key in ("y1", "y5") and ret is None and not row.get("isBenchmark"):
                if iid not in missing_long:
                    missing_long.append(iid)

        # also set on benchmark row
        if row.get("isBenchmark"):
            for key in HORIZON_KEYS:
                row[f"{key}Pct"] = bench_rets[key]
                row[{
                    "m1": "vsNiftyM1",
                    "m3": "vsNiftyM3",
                    "m6": "vsNiftyM6",
                    "y1": "vsNiftyY1",
                    "y5": "vsNiftyY5",
                }[key]] = 0.0 if bench_rets[key] is not None else None

    indices_doc["horizonBasis"] = {
        "asOfArchive": latest_day.isoformat(),
        "lookbacksCalendarDays": HORIZON_DAYS,
        "sources": "NSE archives ind_close_all_*.csv; BSE via Yahoo Finance",
        "missingLongHistory": missing_long,
    }
    # sector rows: only daily/weekly today; leave longer as null-safe
    for sec in indices_doc.get("sectors") or []:
        for key in HORIZON_KEYS:
            sec[f"{key}Pct"] = None
            sec[{
                "m1": "vsNiftyM1",
                "m3": "vsNiftyM3",
                "m6": "vsNiftyM6",
                "y1": "vsNiftyY1",
                "y5": "vsNiftyY5",
            }[key]] = None

    print(
        f"Horizons enriched; y1/y5 missing for {len(missing_long)} indices "
        f"(e.g. {', '.join(missing_long[:8])}{'…' if len(missing_long) > 8 else ''})"
    )
    return indices_doc


def _friday_on_or_before(d: date) -> date:
    return d - timedelta(days=(d.weekday() - 4) % 7)



def build_index_history(
    indices_doc: dict,
    out_path: Path,
    *,
    daily_calendar_days: int = 400,
    weekly_years: int = 5,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Build compact daily (~1Y) + weekly (~5Y) close history for charting.

    Daily: one archive file per calendar day for the last `daily_calendar_days`
    (skips weekends/holidays via 404). Weekly: Friday closes — taken from the
    daily set when possible, otherwise fetched; beyond the daily window we
    sample one Friday per month to keep the backfill fast.
    """
    log = progress or print
    if requests is None:
        log("WARN: requests missing — cannot build index_history")
        return {}

    as_of = date.fromisoformat(indices_doc["asOf"])
    session = _session()
    cache: dict = {}
    seed = fetch_archive_on(as_of, session, cache=cache)
    if not seed:
        log("WARN: no archive seed for history build")
        return {}
    _, seed_closes = seed
    lookup = build_archive_lookup(list(seed_closes.keys()), indices_doc.get("indices") or [])
    id_by_arch = {v: k for k, v in lookup.items()}

    def closes_to_ids(closes: dict[str, float]) -> dict[str, float]:
        row_map: dict[str, float] = {}
        for aname, close in closes.items():
            iid = id_by_arch.get(aname)
            if iid:
                row_map[iid] = round(close, 4)
        for iid, aname in lookup.items():
            if aname in closes and iid not in row_map:
                row_map[iid] = round(closes[aname], 4)
        return row_map

    # --- daily ---
    daily: dict[str, dict[str, float]] = {}
    d = as_of
    end_daily = as_of - timedelta(days=daily_calendar_days)
    while d >= end_daily:
        closes = fetch_archive_exact(d, session, cache)
        if closes:
            m = closes_to_ids(closes)
            if m:
                daily[d.isoformat()] = m
        d -= timedelta(days=1)
        if len(daily) and len(daily) % 50 == 0:
            log(f"  daily history: {len(daily)} sessions…")
        time.sleep(0.04)
    log(f"Daily history: {len(daily)} sessions")

    # --- weekly: Fridays in daily window + monthly Fridays further back ---
    weekly: dict[str, dict[str, float]] = {}
    for ds, m in daily.items():
        if date.fromisoformat(ds).weekday() == 4:
            weekly[ds] = m

    fri = _friday_on_or_before(as_of - timedelta(days=daily_calendar_days))
    end_weekly = as_of - timedelta(days=365 * weekly_years + 14)
    # sample ~1 Friday per month outside daily window
    while fri >= end_weekly:
        key = fri.isoformat()
        if key not in weekly:
            closes = fetch_archive_exact(fri, session, cache)
            if not closes:
                # try Thu / Wed
                for back in (1, 2, 3):
                    closes = fetch_archive_exact(fri - timedelta(days=back), session, cache)
                    if closes:
                        fri_eff = fri - timedelta(days=back)
                        weekly[fri_eff.isoformat()] = closes_to_ids(closes)
                        break
            else:
                weekly[key] = closes_to_ids(closes)
            time.sleep(0.04)
        # jump ~a month
        fri -= timedelta(days=28)
        if len(weekly) and len(weekly) % 30 == 0:
            log(f"  weekly/monthly history: {len(weekly)} points…")
    log(f"Weekly history: {len(weekly)} sessions")

    # BSE from Yahoo
    bse = {"^BSESN": "^BSESN", "BSE-100.BO": "BSE-100.BO", "BSE-500.BO": "BSE-500.BO"}
    for iid, ysym in bse.items():
        series = yahoo_history_series(ysym, years=weekly_years)
        if not series:
            log(f"  WARN: no Yahoo history for {iid}")
            continue
        for grid in (daily, weekly):
            for ds in list(grid.keys()):
                pick = None
                base = date.fromisoformat(ds)
                for offset in range(0, 8):
                    dd = (base - timedelta(days=offset)).isoformat()
                    if dd in series:
                        pick = series[dd]
                        break
                if pick is not None:
                    grid[ds][iid] = pick
        log(f"  merged Yahoo history for {iid} ({len(series)} bars)")

    daily_dates = sorted(daily.keys())
    weekly_dates = sorted(weekly.keys())
    all_ids = sorted({i for m in daily.values() for i in m} | {i for m in weekly.values() for i in m})

    def pack(dates: list[str], grid: dict[str, dict[str, float]]) -> dict:
        series = {}
        for iid in all_ids:
            vals = []
            any_v = False
            for ds in dates:
                v = grid.get(ds, {}).get(iid)
                if v is None:
                    vals.append(None)
                else:
                    vals.append(round(float(v), 2))
                    any_v = True
            if any_v:
                series[iid] = vals
        return {"dates": dates, "series": series}

    coverage = {}
    for iid in all_ids:
        dvals = [daily[ds][iid] for ds in daily_dates if iid in daily.get(ds, {})]
        wvals = [weekly[ds][iid] for ds in weekly_dates if iid in weekly.get(ds, {})]
        coverage[iid] = {
            "dailyBars": len(dvals),
            "weeklyBars": len(wvals),
            "firstDaily": next((ds for ds in daily_dates if iid in daily.get(ds, {})), None),
            "firstWeekly": next((ds for ds in weekly_dates if iid in weekly.get(ds, {})), None),
        }

    doc = {
        "asOf": indices_doc["asOf"],
        "timezone": "Asia/Kolkata",
        "benchmarkId": "NIFTY 50",
        "builtUtc": datetime.now(tz=IST).astimezone().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "NSE archives ind_close_all_*.csv; BSE via Yahoo Finance",
        "daily": pack(daily_dates, daily),
        "weekly": pack(weekly_dates, weekly),
        "coverage": coverage,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    size_kb = out_path.stat().st_size / 1024
    log(
        f"Wrote {out_path} ({size_kb:.0f} KB, {len(all_ids)} series, "
        f"daily={len(daily_dates)}, weekly={len(weekly_dates)})"
    )
    return doc


def refresh_horizons_and_history(indices_doc: dict, data_dir: Path, *, full_history: bool = False) -> dict:
    """Enrich indices_doc in place and write index_history.json."""
    enrich_indices_horizons(indices_doc)
    hist_path = data_dir / "index_history.json"
    if full_history or not hist_path.exists():
        build_index_history(indices_doc, hist_path)
    else:
        # lightweight: rebuild only if file older than asOf or missing series
        try:
            prev = json.loads(hist_path.read_text(encoding="utf-8"))
        except Exception:
            prev = {}
        if prev.get("asOf") != indices_doc.get("asOf") or not prev.get("daily", {}).get("dates"):
            build_index_history(indices_doc, hist_path)
        else:
            print(f"Keeping existing index_history.json (asOf={prev.get('asOf')})")
    return indices_doc


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    data = root / "public" / "data"
    doc = json.loads((data / "indices.json").read_text(encoding="utf-8"))
    refresh_horizons_and_history(doc, data, full_history=True)
    (data / "indices.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    docs = root / "docs" / "data"
    if docs.is_dir():
        for name in ("indices.json", "index_history.json"):
            src = data / name
            if src.exists():
                (docs / name).write_bytes(src.read_bytes())
        print("Synced docs/data/")
