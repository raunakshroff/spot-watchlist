#!/usr/bin/env python3
"""Fetch index constituents + daily % changes for Spot Watchlist.

Membership: niftyindices.com / NSE archives ind_*list.csv (official).
Day change: Yahoo Finance batch on unique .NS symbols (NSE API blocked).
Weights: not published in the list CSVs → null / n/a in the UI.
BSE Sensex / 100 / 500: no reliable open feed from this host → status n/a.

Writes public/data/index_constituents.json (and caller syncs docs/data).
"""

from __future__ import annotations

import csv
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path
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
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public" / "data"

CSV_BASES = (
    "https://www.niftyindices.com/IndexConstituent/",
    "https://archives.nseindia.com/content/indices/",
)

# Curated official CSV map (verified 2026-10-16). Underscore-before-list is
# the modern niftyindices pattern for newer indices.
CONSTITUENT_CSV: dict[str, str] = {
    "NIFTY 100": "ind_nifty100list.csv",
    "NIFTY 200": "ind_nifty200list.csv",
    "NIFTY 50": "ind_nifty50list.csv",
    "NIFTY 500": "ind_nifty500list.csv",
    "NIFTY AUTO": "ind_niftyautolist.csv",
    "NIFTY BANK": "ind_niftybanklist.csv",
    "NIFTY CAPITAL MKT": "ind_niftycapitalmarkets_list.csv",
    "NIFTY CEMENT": "ind_niftycement_list.csv",
    "NIFTY CHEMICALS": "ind_niftychemicals_list.csv",
    "NIFTY COMMODITIES": "ind_niftycommoditieslist.csv",
    "NIFTY CONSR DURBL": "ind_niftyconsumerdurableslist.csv",
    "NIFTY CONSUMPTION": "ind_niftyconsumptionlist.csv",
    "NIFTY COREHOUSING": "ind_niftycorehousing_list.csv",
    "NIFTY CORP MAATR": "ind_niftyindiaselect5corporategroupsmaatr_list.csv",
    "NIFTY CPSE": "ind_niftycpselist.csv",
    "NIFTY ENERGY": "ind_niftyenergylist.csv",
    "NIFTY FIN SERVICE": "ind_niftyfinancelist.csv",
    "NIFTY FINSEREXBNK": "ind_niftyfinancialservicesexbank_list.csv",
    "NIFTY FINSRV25 50": "ind_niftyfinancialservices25_50list.csv",
    "NIFTY FMCG": "ind_niftyfmcglist.csv",
    "NIFTY FPI 150": "ind_niftyindiafpi150_list.csv",
    "NIFTY HEALTHCARE": "ind_niftyhealthcarelist.csv",
    "NIFTY HOUSING": "ind_niftyhousing_list.csv",
    "NIFTY IND DEFENCE": "ind_niftyindiadefence_list.csv",
    "NIFTY IND DIGITAL": "ind_niftyindiadigital_list.csv",
    "NIFTY IND TOURISM": "ind_niftyindiatourism_list.csv",
    "NIFTY INDIA MFG": "ind_niftyindiamanufacturing_list.csv",
    "NIFTY INFRA": "ind_niftyinfralist.csv",
    "NIFTY INTERNET": "ind_niftyindiainternet_list.csv",
    "NIFTY IPO": "ind_niftyipo_list.csv",
    "NIFTY IT": "ind_niftyitlist.csv",
    "NIFTY LARGEMID250": "ind_niftylargemidcap250list.csv",
    "NIFTY M150 QLTY50": "ind_niftymidcap150quality50list.csv",
    "NIFTY MEDIA": "ind_niftymedialist.csv",
    "NIFTY METAL": "ind_niftymetallist.csv",
    "NIFTY MICROCAP250": "ind_niftymicrocap250_list.csv",
    "NIFTY MID SELECT": "ind_niftymidcapselect_list.csv",
    "NIFTY MIDCAP 100": "ind_niftymidcap100list.csv",
    "NIFTY MIDCAP 150": "ind_niftymidcap150list.csv",
    "NIFTY MIDCAP 50": "ind_niftymidcap50list.csv",
    "NIFTY MIDSMALL 50 50": "ind_niftymidsmallcap4005050_list.csv",
    "NIFTY MIDSML 400": "ind_niftymidsmallcap400list.csv",
    "NIFTY MIDSML HLTH": "ind_niftymidsmallhealthcare_list.csv",
    "NIFTY MNC": "ind_niftymnclist.csv",
    "NIFTY MOBILITY": "ind_niftymobility_list.csv",
    "NIFTY MS IND CONS": "ind_niftymidsmallindiaconsumption_list.csv",
    "NIFTY MS IT TELCM": "ind_niftymidsmallitandtelecom_list.csv",
    "NIFTY MULTI INFRA": "ind_nifty500multicapinfrastructure503020_list.csv",
    "NIFTY MULTI MFG": "ind_nifty500multicapindiamanufacturing503020_list.csv",
    "NIFTY MULTI MQ 50": "ind_nifty500multicapmomentumquality50_list.csv",
    "NIFTY NEW CONSUMP": "ind_niftyindianewageconsumption_list.csv",
    "NIFTY NEXT 50": "ind_niftynext50list.csv",
    "NIFTY OIL AND GAS": "ind_niftyoilgaslist.csv",
    "NIFTY PHARMA": "ind_niftypharmalist.csv",
    "NIFTY PSE": "ind_niftypselist.csv",
    "NIFTY PSU BANK": "ind_niftypsubanklist.csv",
    "NIFTY PVT BANK": "ind_nifty_privatebanklist.csv",
    "NIFTY RAILWAYSPSU": "ind_niftyindiarailwayspsu_list.csv",
    "NIFTY REALTY": "ind_niftyrealtylist.csv",
    "NIFTY REITS REALTY": "ind_niftyreitsrealty_list.csv",
    "NIFTY RURAL": "ind_niftyrural_list.csv",
    "NIFTY SERV SECTOR": "ind_niftyservicelist.csv",
    "NIFTY SMALLCAP 500": "ind_niftysmallcap500_list.csv",
    "NIFTY SML250 Q50": "ind_niftysmallcap250quality50_list.csv",
    "NIFTY SMLCAP 100": "ind_niftysmallcap100list.csv",
    "NIFTY SMLCAP 250": "ind_niftysmallcap250list.csv",
    "NIFTY SMLCAP 50": "ind_niftysmallcap50list.csv",
    "NIFTY TATA 25 CAP": "ind_nifty_tata25caplist.csv",
    "NIFTY TMMQ 50": "ind_niftytotalmarketmomentumquality50_list.csv",
    "NIFTY TOP 10 EW": "ind_niftytop10equalweight_list.csv",
    "NIFTY TOP 15 EW": "ind_niftytop15equalweight_list.csv",
    "NIFTY TOP 20 EW": "ind_niftytop20equalweight_list.csv",
    "NIFTY TOTAL MKT": "ind_niftytotalmarket_list.csv",
    "NIFTY TRANS LOGIS": "ind_niftytransportationandlogistics_list.csv",
    "NIFTY WAVES": "ind_niftywaves_list.csv",
    "NIFTY100 ALPHA 30": "ind_nifty100alpha30list.csv",
    "NIFTY100 LOWVOL30": "ind_nifty100lowvolatility30list.csv",
    "NIFTY100 QUALTY30": "ind_nifty100quality30list.csv",
    "NIFTY200 ALPHA 30": "ind_nifty200alpha30_list.csv",
    "NIFTY200 QUALTY30": "ind_nifty200quality30_list.csv",
    "NIFTY200 VALUE 30": "ind_nifty200value30_list.csv",
    "NIFTY200MOMENTM30": "ind_nifty200momentum30_list.csv",
    "NIFTY500 EW": "ind_nifty500equalweight_list.csv",
    "NIFTY500 FLEXICAP": "ind_nifty500flexicapquality30_list.csv",
    "NIFTY500 HEALTH": "ind_nifty500healthcare_list.csv",
    "NIFTY500 LMS EQL": "ind_nifty500largemidsmallequalcapweighted_list.csv",
    "NIFTY500 LOWVOL50": "ind_nifty500lowvolatility50_list.csv",
    "NIFTY500 MQVLV50": "ind_nifty500multifactormqvlv50_list.csv",
    "NIFTY500 MULTICAP": "ind_nifty500multicap502525_list.csv",
    "NIFTY500 QLTY50": "ind_nifty500quality50_list.csv",
    "NIFTY500 VALUE 50": "ind_nifty500value50_list.csv",
    "NIFTY500MOMENTM50": "ind_nifty500momentum50_list.csv",
    "NIFTYCONGLOMERATE": "ind_niftyconglomerate50_list.csv",
    "NIFTYM150MOMNTM50": "ind_niftymidcap150momentum50_list.csv",
    "NIFTYMS400 MQ 100": "ind_niftymidsmallcap400momentumquality100_list.csv",
    "NIFTYSML250MQ 100": "ind_niftysmallcap250momentumquality100_list.csv",
}

BSE_IDS = {"^BSESN", "BSE-100.BO", "BSE-500.BO"}


def _session() -> "requests.Session":
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "text/csv,*/*"})
    return s


def fetch_csv(filename: str, session: "requests.Session") -> list[dict] | None:
    for base in CSV_BASES:
        try:
            r = session.get(base + filename, timeout=20)
        except Exception as e:  # noqa: BLE001
            print(f"WARN: {filename} via {base}: {e}")
            continue
        if r.status_code != 200 or b"Symbol" not in r.content[:500]:
            continue
        rows = list(csv.DictReader(io.StringIO(r.text)))
        if len(rows) >= 1:
            return rows
    return None


def parse_members(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        sym = (row.get("Symbol") or row.get("symbol") or "").strip()
        if not sym:
            continue
        name = (row.get("Company Name") or row.get("Company") or "").strip() or None
        industry = (row.get("Industry") or row.get("Basic Industry") or "").strip() or None
        # weight columns if ever present
        w = None
        for k in ("Weightage", "Weight", "weight", "Weight (%)"):
            if k in row and row[k] not in (None, "", "-"):
                try:
                    w = round(float(str(row[k]).replace("%", "")), 4)
                except ValueError:
                    w = None
                break
        out.append(
            {
                "symbol": sym,
                "name": name,
                "industry": industry,
                "weight": w,
                "dailyPct": None,
                "onWatchlist": False,
            }
        )
    return out


def yahoo_daily_pcts(symbols: list[str]) -> dict[str, float | None]:
    """Batch 5d history → last daily % for NSE symbols."""
    if not symbols or yf is None:
        return {}
    tickers = [f"{s}.NS" for s in symbols]
    out: dict[str, float | None] = {s: None for s in symbols}
    # chunk to avoid huge single requests
    for i in range(0, len(tickers), 80):
        chunk = tickers[i : i + 80]
        try:
            df = yf.download(
                chunk,
                period="5d",
                group_by="ticker",
                threads=True,
                progress=False,
                auto_adjust=True,
            )
        except Exception as e:  # noqa: BLE001
            print(f"WARN: yfinance batch {i}: {e}")
            time.sleep(1)
            continue
        import pandas as pd

        for t in chunk:
            sym = t[: -len(".NS")]
            try:
                if isinstance(df.columns, pd.MultiIndex):
                    if t not in df.columns.get_level_values(0):
                        continue
                    closes = df[t]["Close"].dropna()
                else:
                    closes = df["Close"].dropna()
                if len(closes) >= 2:
                    a, b = float(closes.iloc[-2]), float(closes.iloc[-1])
                    if a:
                        out[sym] = round((b / a - 1.0) * 100, 2)
            except Exception:
                continue
        time.sleep(0.2)
    return out


def watchlist_symbols(path: Path) -> set[str]:
    if not path.exists():
        return set()
    wl = json.loads(path.read_text(encoding="utf-8"))
    out = set()
    for s in wl:
        t = (s.get("ticker") or "").replace(".NS", "").replace(".BO", "").strip().upper()
        if t:
            out.add(t)
    return out


def build_constituents(
    *,
    refresh_membership: bool = True,
    refresh_prices: bool = True,
    existing: dict | None = None,
) -> dict:
    if requests is None:
        raise RuntimeError("requests required")

    indices = json.loads((DATA / "indices.json").read_text(encoding="utf-8"))
    ids = [r["id"] for r in indices.get("indices") or []]
    wl = watchlist_symbols(DATA / "watchlist.json")
    session = _session()

    prev = existing or {}
    if not prev and (DATA / "index_constituents.json").exists():
        try:
            prev = json.loads((DATA / "index_constituents.json").read_text(encoding="utf-8"))
        except Exception:
            prev = {}
    prev_by_id = {x["id"]: x for x in (prev.get("indices") or []) if x.get("id")}

    by_id: dict[str, dict] = {}
    missing: list[dict] = []

    for iid in ids:
        if iid in BSE_IDS:
            by_id[iid] = {
                "id": iid,
                "status": "n/a",
                "reason": "BSE constituents not available from open feed",
                "count": 0,
                "members": [],
                "csv": None,
                "membershipAsOf": None,
            }
            missing.append({"id": iid, "reason": "bse"})
            continue

        fname = CONSTITUENT_CSV.get(iid)
        members = None
        csv_name = None
        mem_asof = None

        if refresh_membership and fname:
            rows = fetch_csv(fname, session)
            time.sleep(0.05)
            if rows:
                members = parse_members(rows)
                csv_name = fname
                mem_asof = datetime.now(IST).strftime("%Y-%m-%d")
            else:
                print(f"WARN: CSV empty/missing for {iid} ({fname})")

        if members is None and iid in prev_by_id and prev_by_id[iid].get("members"):
            # keep prior membership
            old = prev_by_id[iid]
            members = [
                {
                    "symbol": m["symbol"],
                    "name": m.get("name"),
                    "industry": m.get("industry"),
                    "weight": m.get("weight"),
                    "dailyPct": m.get("dailyPct") if not refresh_prices else None,
                    "onWatchlist": False,
                }
                for m in old["members"]
            ]
            csv_name = old.get("csv")
            mem_asof = old.get("membershipAsOf")

        if not members:
            by_id[iid] = {
                "id": iid,
                "status": "n/a",
                "reason": "no official constituent CSV found",
                "count": 0,
                "members": [],
                "csv": fname,
                "membershipAsOf": None,
            }
            missing.append({"id": iid, "reason": "no-csv"})
            continue

        by_id[iid] = {
            "id": iid,
            "status": "ok",
            "reason": None,
            "count": len(members),
            "members": members,
            "csv": csv_name,
            "membershipAsOf": mem_asof,
        }

    # day changes
    if refresh_prices:
        all_syms = sorted(
            {
                m["symbol"]
                for block in by_id.values()
                for m in block.get("members") or []
                if m.get("symbol")
            }
        )
        print(f"Fetching daily % for {len(all_syms)} unique symbols…")
        pcts = yahoo_daily_pcts(all_syms)
        hit = sum(1 for v in pcts.values() if v is not None)
        print(f"  got {hit}/{len(all_syms)} day changes")
        for block in by_id.values():
            for m in block.get("members") or []:
                m["dailyPct"] = pcts.get(m["symbol"])
                m["onWatchlist"] = m["symbol"].upper() in wl
    else:
        for block in by_id.values():
            for m in block.get("members") or []:
                m["onWatchlist"] = m["symbol"].upper() in wl

    with_c = sum(1 for b in by_id.values() if b["status"] == "ok")
    without = len(by_id) - with_c
    doc = {
        "asOf": datetime.now(IST).strftime("%Y-%m-%d"),
        "timezone": "Asia/Kolkata",
        "lastRunUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "niftyindices.com / NSE archives IndexConstituent CSVs; day change via Yahoo Finance",
        "weightNote": "Official list CSVs do not include weights; weight shown as n/a",
        "counts": {"withConstituents": with_c, "withoutConstituents": without, "total": len(by_id)},
        "missing": missing,
        "indices": [by_id[i] for i in ids if i in by_id],
    }
    return doc


def save(doc: dict) -> Path:
    path = DATA / "index_constituents.json"
    path.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Wrote {path} ({path.stat().st_size/1024:.0f} KB) "
        f"with={doc['counts']['withConstituents']} without={doc['counts']['withoutConstituents']}"
    )
    return path


def refresh(*, force_membership: bool = False) -> dict:
    """Daily: refresh prices. Weekly (Mon or force): refresh membership CSVs."""
    weekday = datetime.now(IST).weekday()  # Mon=0
    refresh_mem = force_membership or weekday == 0
    doc = build_constituents(refresh_membership=refresh_mem, refresh_prices=True)
    save(doc)
    return doc


if __name__ == "__main__":
    import sys

    force = "--force-membership" in sys.argv
    doc = refresh(force_membership=force or True)
    docs = ROOT / "docs" / "data"
    if docs.is_dir():
        (docs / "index_constituents.json").write_bytes((DATA / "index_constituents.json").read_bytes())
        print("Synced docs/data/index_constituents.json")
