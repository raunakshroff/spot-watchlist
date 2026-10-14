#!/usr/bin/env python3
"""Ingest a Sovrenn Times daily edition (PDF or pdftotext -layout .txt) into
public/data/sovrenn.json (a separate list, NOT the active watchlist).

Usage:
  python scripts/sovrenn_ingest.py EDITION.pdf [EDITION2.pdf ...] [--date YYYY-MM-DD] [--no-prices]

Edition format (as of Oct 2026): page 3-4 "Sovrenn Times - 6 News Summary"
lists 6 numbered companies, each with "Filing: (TAG) text", "MCap: INR x Crore
PE: y". Pages 6+ hold one detail section per company whose header carries the
exchange code (NSE:/NSE-SME:/BSE:/BSE-SME:), "(1st time covered: ...)" and a
"FUTURE OUTLOOK:" paragraph. All quoted text is stored verbatim.

Idempotent: re-ingesting the same edition (e.g. a duplicate send) does not
double-count mentions; entries are keyed by symbol and mention by date.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public" / "data"
DOCS_DATA = ROOT / "docs" / "data"
FILE = "sovrenn.json"
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def to_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return subprocess.run(["pdftotext", "-layout", str(path), "-"],
                              check=True, capture_output=True, text=True).stdout
    return path.read_text(encoding="utf-8")


def parse_date(s: str) -> str | None:
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3})[a-z]*\s+(\d{4})", s)
    if not m:
        return None
    return f"{int(m.group(3)):04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_edition(text: str) -> dict:
    lines = text.splitlines()
    # page headers are a right-aligned date line ("13th Oct 2026"); take the most common
    from collections import Counter
    hdr = [parse_date(ln) for ln in lines if re.fullmatch(r"\s*\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\s+\d{4}\s*", ln)]
    edition_date = Counter(d for d in hdr if d).most_common(1)[0][0] if any(hdr) else None
    start = next(i for i, ln in enumerate(lines) if "News Summary" in ln)
    item_re = re.compile(r"^ ?(\d)\. ([A-Z0-9].*)$")
    # summary items: flush-left numbered lines; detail headers: leading space
    summary_idx, detail_idx = [], []
    for i in range(start, len(lines)):
        m = item_re.match(lines[i])
        if not m:
            continue
        nxt = " ".join(lines[i:i + 3])
        if lines[i].startswith(" ") and ("1st time covered" in nxt or "NSE" in lines[i] or "BSE" in lines[i] or "LIMITED" in lines[i + 1]):
            if "Recent Filing" in " ".join(lines[i:i + 6]):
                detail_idx.append(i)
        elif not lines[i].startswith(" ") and "Filing:" in " ".join(lines[i:i + 3]):
            summary_idx.append(i)
    items: dict[int, dict] = {}
    for i in summary_idx:
        n = int(item_re.match(lines[i]).group(1))
        name = re.sub(r"\s*-\s*$", "", lines[i].split(". ", 1)[1]).strip()
        j, buf = i + 1, []
        while j < len(lines) and not lines[j].startswith("MCap"):
            buf.append(lines[j]); j += 1
        filing = clean(" ".join(buf)).removeprefix("Filing:").strip()
        mcap = pe = None
        if j < len(lines):
            mm = re.search(r"MCap:\s*(.+?Crore)", lines[j]); mcap = mm.group(1) if mm else None
            pm = re.search(r"PE:\s*(\S+)", lines[j]); pe = pm.group(1) if pm else None
        tag = re.match(r"\(([^)]+)\)", filing)
        items[n] = {"n": n, "name": name, "tag": tag.group(1) if tag else None,
                    "filing": filing, "sovrennMcap": mcap, "sovrennPe": pe}
    for i in detail_idx:
        n = int(item_re.match(lines[i]).group(1))
        hdr, j = [], i
        while j < len(lines) and "Recent Filing" not in lines[j]:
            hdr.append(lines[j]); j += 1
        h = clean(" ".join(hdr)).replace("NSE- SME", "NSE-SME").replace("BSE- SME", "BSE-SME")
        codes = {}
        for ex, val in re.findall(r"\b(NSE-SME|BSE-SME|NSE|BSE):\s*([A-Z0-9&\-]+)", h):
            codes.setdefault(ex, val)
        paren = re.search(r"BSE(?:-SME)?:\s*\d+\s*\(([A-Z0-9]+)\)", h)
        if paren:
            codes.setdefault("BSE_SYMBOL", paren.group(1))
        isin = re.search(r"ISIN:\s*([A-Z0-9]{12})", h)
        first = re.search(r"1st time covered:\s*([^)]+)\)", h)
        # future outlook paragraph
        k, outlook = j, []
        while k < min(len(lines), j + 60):
            if "FUTURE OUTLOOK:" in lines[k]:
                while k < len(lines) and lines[k].strip():
                    outlook.append(lines[k]); k += 1
                break
            k += 1
        it = items.setdefault(n, {"n": n})
        it.update({"codes": codes, "isin": isin.group(1) if isin else None,
                   "sme": "SME" in h, "firstCoveredBySovrenn": parse_date(first.group(1)) if first else None,
                   "outlook": clean(" ".join(outlook)).removeprefix("FUTURE OUTLOOK:").strip() or None})
    return {"date": edition_date, "items": [items[k] for k in sorted(items)]}


def candidate_tickers(it: dict) -> list[str]:
    c = it.get("codes", {})
    out = []
    for ex in ("NSE", "NSE-SME"):
        if ex in c and not c[ex].isdigit():
            out.append(c[ex] + ".NS")
    for ex in ("BSE", "BSE-SME"):
        if ex in c:
            out.append(c[ex] + ".BO")
    if "BSE_SYMBOL" in c:
        out.append(c["BSE_SYMBOL"] + ".BO")
    return out


def load_db() -> list[dict]:
    p = DATA / FILE
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save_db(db: list[dict]) -> None:
    txt = json.dumps(db, indent=2, ensure_ascii=False) + "\n"
    (DATA / FILE).write_text(txt, encoding="utf-8")
    if DOCS_DATA.is_dir():
        (DOCS_DATA / FILE).write_text(txt, encoding="utf-8")


def key_for(it: dict) -> str:
    c = it.get("codes", {})
    return c.get("NSE") or c.get("NSE-SME") or c.get("BSE_SYMBOL") or c.get("BSE") or c.get("BSE-SME") \
        or it.get("isin") or it["name"]


def merge(db: list[dict], ed: dict) -> int:
    by_key = {e["key"]: e for e in db}
    added = 0
    for it in ed["items"]:
        k = key_for(it)
        e = by_key.get(k)
        mention = {"date": ed["date"], "tag": it.get("tag"), "filing": it.get("filing"),
                   "outlook": it.get("outlook"), "sovrennMcap": it.get("sovrennMcap"),
                   "sovrennPe": it.get("sovrennPe")}
        if e is None:
            e = {"key": k, "name": it["name"].title(), "nameRaw": it["name"], "codes": it.get("codes", {}),
                 "isin": it.get("isin"), "sme": it.get("sme", False),
                 "candidates": candidate_tickers(it), "ticker": None,
                 "firstCoveredBySovrenn": it.get("firstCoveredBySovrenn"),
                 "mentions": []}
            db.append(e); by_key[k] = e; added += 1
        e["mentions"] = [m for m in e["mentions"] if m["date"] != ed["date"]] + [mention]
        e["mentions"].sort(key=lambda m: m["date"])
        e["firstHighlighted"] = e["mentions"][0]["date"]
        e["timesMentioned"] = len(e["mentions"])
        last = e["mentions"][-1]
        e["latestDate"] = last["date"]
        e["latestTag"] = last["tag"]
        e["latestReason"] = last["filing"]
        e["latestOutlook"] = last["outlook"] or e.get("latestOutlook")
        e["sovrennMcap"] = last["sovrennMcap"]
        e["sovrennPe"] = last["sovrennPe"]
    db.sort(key=lambda e: (e["latestDate"], e["key"]), reverse=True)
    return added


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--date", help="override edition date YYYY-MM-DD")
    ap.add_argument("--no-prices", action="store_true", help="skip yfinance refresh")
    a = ap.parse_args()
    db = load_db()
    seen = set()
    for f in a.files:
        ed = parse_edition(to_text(Path(f)))
        if a.date:
            ed["date"] = a.date
        if ed["date"] in seen:
            print(f"skip duplicate edition {ed['date']} ({f})"); continue
        seen.add(ed["date"])
        n = merge(db, ed)
        print(f"{ed['date']}: {len(ed['items'])} items, {n} new companies")
    if not a.no_prices:
        sys.path.insert(0, str(Path(__file__).parent))
        from sovrenn_prices import refresh
        refresh(db)
    save_db(db)
    print(f"sovrenn.json: {len(db)} companies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
