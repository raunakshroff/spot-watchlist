"""Order tracker: pull order-win / contract filings for every tracked company.

Sources
- NSE corporate announcements API (main board + SME) for .NS tickers
- screener.in company page "Announcements" (BSE filings) for BSE-only .BO tickers

Writes public/data/orders.json (+ docs/data copy) and writes the orders that are
new in this run to --new-out (default /tmp/orders_new.json) so a nightly job can
email them. Idempotent: filings already in orders.json are skipped.

Usage: python scripts/orders_ingest.py [--days 90] [--new-out PATH] [--only SYM,SYM]
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public" / "data"
DOCS_DATA = ROOT / "docs" / "data"
OUT = DATA / "orders.json"
IST = ZoneInfo("Asia/Kolkata")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
NSE_HDR = {"User-Agent": UA, "Accept": "application/json,text/plain,*/*", "Referer": "https://www.nseindia.com/"}

ORDER_KW = re.compile(
    r"\b(orders?|contracts?|lo[ai]s?|letter of (award|intent|acceptance)|work orders?|purchase orders?|"
    r"awarded|bagg(ed|ing)|secured|l-?1 bidder|h-?1 bidder|lowest bidder|empanel\w*)\b",
    re.I,
)
NOT_ORDER = re.compile(
    r"in order to|order of the (hon|court|tribunal)|court|tribunal|nclt|penalty|show cause|gst|tax|"
    r"assessment order|demand order|income tax|interim order|arbitra|sebi order|adjudicat|"
    r"trading window|esop|allotment of|financial result|board meeting|newspaper",
    re.I,
)


# ---------------------------------------------------------------- universe
def tracked() -> dict[str, dict]:
    """ticker -> {ticker, name, segments}"""
    out: dict[str, dict] = {}

    def add(t, name, seg, extra=None):
        if not t:
            return
        e = out.setdefault(t, {"ticker": t, "name": name, "segments": []})
        if seg not in e["segments"]:
            e["segments"].append(seg)
        if extra:
            e.update({k: v for k, v in extra.items() if v})

    for s in json.loads((DATA / "watchlist.json").read_text()):
        add(s.get("ticker"), s.get("name"), "Active")
    ev = json.loads((DATA / "events.json").read_text())
    for e in ev.get("events", []):
        for c in e.get("companies", []):
            add(c.get("ticker"), c.get("name"), "Events")
    for s in json.loads((DATA / "sovrenn.json").read_text()):
        add(s.get("ticker"), s.get("name"), "Sovrenn",
            {"bseCode": (s.get("codes") or {}).get("BSE-SME") or (s.get("codes") or {}).get("BSE"), "sovrennMcapCr": s.get("mcapCr")})
    return out


# ---------------------------------------------------------------- fetchers
def nse_announcements(sym: str, sme: bool, frm: date, to: date) -> list[dict]:
    url = (f"https://www.nseindia.com/api/corporate-announcements?index={'sme' if sme else 'equities'}"
           f"&symbol={requests.utils.quote(sym)}&from_date={frm:%d-%m-%Y}&to_date={to:%d-%m-%Y}")
    for attempt in range(3):
        try:
            r = requests.get(url, headers=NSE_HDR, timeout=30)
            if r.status_code == 200:
                d = r.json()
                return d if isinstance(d, list) else d.get("data", [])
        except Exception:
            pass
        time.sleep(2 + attempt * 3)
    raise RuntimeError(f"NSE fetch failed for {sym}")


def screener_announcements(code: str, name: str | None = None) -> list[dict]:
    r = requests.get(f"https://www.screener.in/company/{code}/", headers={"User-Agent": UA}, timeout=30)
    if r.status_code == 404 and name:
        q = re.sub(r"\b(limited|ltd\.?)\b", "", name, flags=re.I).strip()
        hits = requests.get("https://www.screener.in/api/company/search/", params={"q": q},
                            headers={"User-Agent": UA}, timeout=30).json()
        if hits:
            r = requests.get(f"https://www.screener.in{hits[0]['url']}", headers={"User-Agent": UA}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"screener {code}: {r.status_code}")
    h = r.text
    i = h.find('id="documents"')
    seg = h[i:i + 20000] if i >= 0 else ""
    out = []
    for m in re.finditer(r'<a[^>]+href="([^"]+AnnPdfOpen[^"]+|[^"]+corpfiling[^"]+)"[^>]*>(.*?)</a>', seg, re.S):
        txt = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        out.append({"url": m.group(1), "text": txt})
    return out


def pdf_text(url: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        subprocess.run(["curl", "-s", "-L", "-A", UA, "--max-time", "90", "-o", f.name, url], check=False)
        try:
            return subprocess.run(["pdftotext", "-layout", "-l", "6", f.name, "-"],
                                  capture_output=True, text=True, timeout=60).stdout
        except Exception:
            return ""


# ---------------------------------------------------------------- extraction
NUM = r"([\d]{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
UNIT = r"(crores?|crs?\.?|cr\b|lakhs?|lacs?|million|mn\b|billion|bn\b)"
INR_AMT = re.compile(r"(?:rs\.?|inr|₹|rupees)\s*" + NUM + r"\s*(?:/-)?\s*" + UNIT + "?", re.I)
BARE_CR = re.compile(NUM + r"\s*(crores?|crs?\.?|cr\b)", re.I)
USD_AMT = re.compile(r"(?:usd|us\s?\$|\$)\s*" + NUM + r"\s*" + UNIT + "?", re.I)
EUR_AMT = re.compile(r"(?:eur|€)\s*" + NUM + r"\s*" + UNIT + "?", re.I)
VALUE_CTX = re.compile(r"total|worth|valu|aggregat|amount|consideration|size|order of|contract price|cost", re.I)
BAD_CTX = re.compile(r"turnover|net ?worth|share capital|penalty|revenue|pat\b|profit|ebitda|market cap|paid.?up|"
                     r"order ?book|bank guarantee|earnest|emd|security deposit|fine", re.I)


def _to_cr(n: float, unit: str | None, fx: float = 1.0) -> float | None:
    u = (unit or "").lower()
    if u.startswith(("cr",)):
        v = n
    elif u.startswith(("lakh", "lac")):
        v = n / 100
    elif u.startswith(("million", "mn")):
        v = n / 10
    elif u.startswith(("billion", "bn")):
        v = n * 100
    else:
        v = n / 1e7  # plain rupees / dollars
    v *= fx
    return round(v, 2) if v >= 0.01 else None


def extract_value(text: str, usdinr: float, eurinr: float) -> float | None:
    t = re.sub(r"\s+", " ", text)
    sents = re.split(r"(?<=[.;:])\s+|\n", t)
    cands: list[tuple[int, float]] = []
    for idx, s in enumerate(sents):
        if re.search(r"order ?book|order inflow|backlog|multinational|market cap", s, re.I):
            continue
        if BAD_CTX.search(s) and not re.search(r"order|contract", s, re.I):
            continue
        score = 2 if VALUE_CTX.search(s) else 0
        if re.search(r"order|contract|loa|award|lo[ia]\b", s, re.I):
            score += 1
        if BAD_CTX.search(s):
            score -= 2
        for rx, fx in ((INR_AMT, 1.0), (BARE_CR, 1.0), (USD_AMT, usdinr), (EUR_AMT, eurinr)):
            for m in rx.finditer(s):
                try:
                    n = float(m.group(1).replace(",", ""))
                except ValueError:
                    continue
                unit = m.group(2) if m.lastindex and m.lastindex >= 2 else None
                if rx is BARE_CR:
                    unit = m.group(2)
                if not unit and n < 1e5:
                    continue
                v = _to_cr(n, unit, fx)
                if v:
                    cands.append((score * 1000 - idx, v))
    if not cands:
        return None
    cands.sort(reverse=True)
    return cands[0][1]


CLASS_RANGES = {
    "ultra-mega": "₹15,000 Cr+", "ultra mega": "₹15,000 Cr+", "mega": "₹10,000–15,000 Cr", "major": "₹5,000–10,000 Cr",
    "large": "₹2,500–5,000 Cr", "significant": "₹1,000–2,500 Cr",
}


def classification_range(text: str) -> str | None:
    """L&T-style filings give a size band ('large*' order) instead of a value."""
    if not re.search(r"order classification", text, re.I):
        return None
    t = re.sub(r"\s+", " ", text).lower()
    for k in ("ultra-mega", "ultra mega", "mega", "major", "large", "significant"):
        if re.search(rf"\b{k}\s*\*|\b{k}\*? (order|contract)s?\b", t):
            return f"{CLASS_RANGES[k]} ({k.replace(' ', '-')} band)"
    return None


def _right_col(lines: list[str], i: int) -> str:
    """Text in the right-hand column of a layout table starting at line i."""
    parts = []
    for j in range(i, min(i + 4, len(lines))):
        cols = re.split(r"\s{3,}", lines[j].strip())
        if len(cols) >= 2:
            right = cols[-1].strip()
            if j > i and re.match(r"^\d+\.?\s", lines[j].strip()):
                break
            parts.append(right)
        elif j > i:
            break
    return re.sub(r"\s+", " ", " ".join(parts)).strip(" ;:.")


def extract_customer(text: str) -> str | None:
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if re.search(r"name of the entity awarding|awarding (entity|authority)|name of (the )?(client|customer)", ln, re.I):
            v = _right_col(lines, i)
            v = re.sub(r"^(the )?order\(s\)/contract\(s\);?", "", v, flags=re.I).strip()
            if v and len(v) > 2 and not re.search(r"entity awarding", v, re.I):
                return v[:90]
    t = re.sub(r"\s+", " ", text)
    pats = [
        r"(?:received|bagged|secured|obtained)[^.]{0,80}?\bfrom\s+(?:m/s\.?\s*)?(?:the\s+)?([A-Z][\w&.,()'\- ]{3,90}?)(?=\s+(?:for|towards|worth|valued|amounting|aggregating|vide|dated|under|to supply|on)\b|[,;]|\.\s)",
        r"\bfrom\s+m/s\.?\s*([A-Z][\w&.,()'\- ]{3,90}?)(?=\s+(?:for|towards|worth|valued|amounting|vide|dated)\b|[,;]|\.\s)",
        r"awarded by\s+(?:m/s\.?\s*)?(?:the\s+)?([A-Z][\w&.,()'\- ]{3,90}?)(?=\s+(?:for|towards|worth|valued|amounting|vide|dated)\b|[,;]|\.\s)",
    ]
    for p in pats:
        m = re.search(p, t, re.I)
        if m:
            v = m.group(1).strip(" .,")
            if not re.match(r"(the exchange|exchange|bse|nse|national stock)", v, re.I):
                return v[:90]
    return None


def extract_duration_months(text: str) -> float | None:
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if re.search(r"time period.{0,40}execut|period of execution|completion period|execution period", ln, re.I):
            v = _right_col(lines, i)
            d = _dur(v)
            if d:
                return d
    t = re.sub(r"\s+", " ", text)
    for s in re.split(r"(?<=[.;])\s+", t):
        if re.search(r"deliver|execut|complet|period|tenure|within|duration|implement", s, re.I):
            d = _dur(s)
            if d:
                return d
    return None


MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def until_months(s: str, ref: date) -> float | None:
    m = re.search(r"(?:up ?to|till|until|by)\s+(?:end of\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*,?\s+(20\d\d)", s, re.I)
    if not m:
        return None
    n = (int(m.group(2)) - ref.year) * 12 + MONTHS[m.group(1).lower()] - ref.month
    return float(n) if 0 < n <= 240 else None


def _dur(s: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to|–|—)?\s*(\d+(?:\.\d+)?)?\s*\(?\w*\)?\s*(months?|years?|yrs?|days?|weeks?)\b", s, re.I)
    if not m:
        return None
    n = float(m.group(2) or m.group(1))
    u = m.group(3).lower()
    if u.startswith(("year", "yr")):
        n *= 12
    elif u.startswith("day"):
        n /= 30
    elif u.startswith("week"):
        n /= 4.345
    return round(n, 1) if 0 < n <= 240 else None


def extract_type(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(l-?1|lowest bidder|h-?1 bidder|emerged as)", t) and not re.search(r"letter of (award|acceptance)|\bloa\b", t):
        return "L1 / Bid"
    if re.search(r"letter of intent|\bloi\b", t):
        return "LOI"
    if re.search(r"letter of (award|acceptance)|\bloa\b", t):
        return "LoA"
    if re.search(r"purchase order|\bpo\b", t):
        return "Purchase Order"
    if re.search(r"work order", t):
        return "Work Order"
    if re.search(r"empanel", t):
        return "Empanelment"
    if re.search(r"contract", t):
        return "Contract"
    if re.search(r"order", t):
        return "Order"
    return "Not mentioned"


def extract_scope(text: str) -> str | None:
    m = re.search(r"\b(international|overseas|export)\b", text, re.I)
    d = re.search(r"\bdomestic\b", text, re.I)
    if d and not m:
        return "Domestic"
    if m and not d:
        return "International"
    return None


# ---------------------------------------------------------------- market data
def fx_rates() -> tuple[float, float]:
    import yfinance as yf
    out = []
    for p, dflt in (("USDINR=X", 88.0), ("EURINR=X", 102.0)):
        try:
            out.append(float(yf.Ticker(p).history(period="5d")["Close"].dropna().iloc[-1]))
        except Exception:
            out.append(dflt)
    return out[0], out[1]


def fundamentals(ticker: str) -> dict:
    import yfinance as yf
    tk = yf.Ticker(ticker)
    res = {"mcapCr": None, "revenueCr": None, "revenueBasis": None}
    try:
        info = tk.info or {}
        if info.get("marketCap"):
            res["mcapCr"] = round(info["marketCap"] / 1e7, 1)
        if info.get("totalRevenue"):
            res["revenueCr"] = round(info["totalRevenue"] / 1e7, 1)
            res["revenueBasis"] = "TTM"
    except Exception:
        pass
    if res["revenueCr"] is None:
        try:
            fin = tk.income_stmt
            if fin is not None and not fin.empty and "Total Revenue" in fin.index:
                col = fin.columns[0]
                v = fin.loc["Total Revenue", col]
                if v == v:
                    res["revenueCr"] = round(float(v) / 1e7, 1)
                    res["revenueBasis"] = f"FY{str(col.year)[2:]}"
        except Exception:
            pass
    return res


def price_reaction(hist, ann: datetime) -> dict:
    """% move from the last close before the filing to the close N sessions after."""
    out = {"d1": None, "d3": None, "d5": None}
    if hist is None or hist.empty:
        return out
    closes = hist["Close"].dropna()
    idx = [d.date() for d in closes.index]
    ad = ann.date()
    after_close = ann.hour > 15 or (ann.hour == 15 and ann.minute >= 30)
    base_i = None
    for i, d in enumerate(idx):
        if d < ad or (d == ad and after_close):
            base_i = i
    if base_i is None:
        return out
    base = float(closes.iloc[base_i])
    for n, k in ((1, "d1"), (3, "d3"), (5, "d5")):
        j = base_i + n
        if j < len(closes):
            out[k] = round((float(closes.iloc[j]) / base - 1) * 100, 2)
    return out


# ---------------------------------------------------------------- main
def parse_nse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%d-%b-%Y %H:%M:%S").replace(tzinfo=IST)


RESULTS = re.compile(r"\bresults?\b|\bq[1-4]\b|quarter|half year|h1 fy|order ?book|earnings|investor presentation", re.I)


def is_order_filing(desc: str, text: str) -> bool:
    if desc.lower().startswith("bagging/receiving of orders"):
        return True
    if RESULTS.search(text) or re.search(r"action\(s\) taken or orders passed", text, re.I):
        return False
    if NOT_ORDER.search(text) and not re.search(r"order wins?|receives? orders?|bag", text, re.I):
        return False
    if desc.lower() in ("press release", "general updates", "updates", "awarding of order(s)/contract(s)", "receipt of order") \
            or "order" in desc.lower() or "contract" in desc.lower():
        return bool(ORDER_KW.search(text)) and bool(re.search(r"order|contract|lo[ai]\b|letter of|award|bidder", text, re.I))
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=10, help="lookback window (backfill: 90)")
    ap.add_argument("--new-out", default="/tmp/orders_new.json")
    ap.add_argument("--only", default="")
    ap.add_argument("--reprocess", action="store_true", help="re-extract stored orders with current rules")
    ap.add_argument("--checkpoint", default="", help="resume file for long backfills")
    a = ap.parse_args()

    store = json.loads(OUT.read_text()) if OUT.exists() else {"orders": [], "companies": {}}
    known = {o["id"] for o in store["orders"]}
    uni = tracked()
    if a.only:
        keep = {x.strip().upper() for x in a.only.split(",")}
        uni = {k: v for k, v in uni.items() if k.split(".")[0].upper() in keep or k.upper() in keep}
    today = datetime.now(IST).date()
    frm = today - timedelta(days=a.days)
    usdinr, eurinr = fx_rates()
    errors: list[str] = []
    fresh: list[dict] = []
    ck = {"done": [], "fresh": []}
    if a.checkpoint and Path(a.checkpoint).exists():
        ck = json.loads(Path(a.checkpoint).read_text())
        fresh = ck["fresh"]
        known |= {o["id"] for o in fresh}

    if a.reprocess:
        redo = []
        for o in store["orders"]:
            if RESULTS.search(o.get("summary", "")) and not o["summary"].lower().startswith("bagging"):
                continue
            c = uni.get(o["ticker"], {"name": o["company"], "segments": o["segments"]})
            body = pdf_text(o["pdf"])
            if RESULTS.search(body[:1500]) and re.search(r"press release", o.get("summary", ""), re.I):
                continue
            n = build(o["id"], o["ticker"], c, datetime.fromisoformat(o["announcedAt"]), o["summary"], body, o["pdf"],
                      o["source"], usdinr, eurinr)
            n.update({k: o.get(k) for k in ("d1", "d3", "d5")})
            redo.append(n)
        store["orders"] = redo
        uni = {}

    for t, c in sorted(uni.items()):
        seg = c["segments"]
        if t in ck["done"]:
            continue
        print("..", t, flush=True)
        try:
            if t.endswith(".NS"):
                base = t[:-3]
                sme = bool(re.search(r"-(SM|ST)$", base))
                sym = re.sub(r"-(SM|ST)$", "", base)
                rows = nse_announcements(sym, sme, frm, today)
                pr_rows, bag_rows = [], []
                for x in rows:
                    desc = x.get("desc") or ""
                    txt = html.unescape(x.get("attchmntText") or "")
                    if not is_order_filing(desc, f"{desc} {txt}"):
                        continue
                    (bag_rows if desc.lower().startswith("bagging") else pr_rows).append(x)
                bag_days = {parse_nse_dt(x["an_dt"]).date() for x in bag_rows}
                for x in pr_rows:  # press release duplicating a same/next-day Bagging filing
                    d = parse_nse_dt(x["an_dt"]).date()
                    if any(abs((d - b).days) <= 1 for b in bag_days):
                        continue
                    bag_rows.append(x)
                for x in bag_rows:
                    oid = f"NSE-{x['seq_id']}"
                    if oid in known:
                        continue
                    ann = parse_nse_dt(x["an_dt"])
                    head = html.unescape(x.get("attchmntText") or "")
                    url = x.get("attchmntFile") or ""
                    body = pdf_text(url) if url.lower().endswith(".pdf") else ""
                    fresh.append(build(oid, t, c, ann, head, body, url, "NSE", usdinr, eurinr))
                    time.sleep(0.4)
                time.sleep(0.6)
            elif t.endswith(".BO"):
                code = c.get("bseCode") or t[:-3]
                for d in screener_announcements(code, c.get("name")):
                    txt = d["text"]
                    m = re.search(r"\b(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", txt)
                    if not m:
                        continue
                    dd = datetime.strptime(f"{m.group(1)} {m.group(2)} {today.year}", "%d %b %Y").date()
                    if dd > today:
                        dd = dd.replace(year=today.year - 1)
                    if dd < frm:
                        continue
                    title = txt[:m.start()].strip()
                    if not (re.search(r"order|contract|award|lo[ai]\b|letter of", title, re.I) and
                            is_order_filing("updates", txt)):
                        continue
                    pid = re.search(r"([0-9a-f\-]{30,})\.pdf", d["url"], re.I)
                    oid = f"BSE-{pid.group(1) if pid else abs(hash(d['url']))}"
                    if oid in known:
                        continue
                    pdf_url = d["url"]
                    if pid:
                        pdf_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{pid.group(1)}.pdf"
                    body = pdf_text(pdf_url)
                    if len(body.strip()) < 50:
                        pdf_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachHis/{pid.group(1)}.pdf" if pid else d["url"]
                        body = pdf_text(pdf_url)
                    ann = datetime(dd.year, dd.month, dd.day, 12, 0, tzinfo=IST)
                    fresh.append(build(oid, t, c, ann, txt, body, pdf_url, "BSE (via screener.in)", usdinr, eurinr))
                time.sleep(1.5)
        except Exception as e:  # keep going; report at the end
            errors.append(f"{t}: {e}")
        if a.checkpoint:
            ck["done"].append(t)
            ck["fresh"] = fresh
            Path(a.checkpoint).write_text(json.dumps(ck))

    # fundamentals + reactions (refresh for every company that has orders)
    import yfinance as yf
    all_orders = store["orders"] + fresh
    syms = sorted({o["ticker"] for o in all_orders})
    comp = store.get("companies", {})
    for s in syms:
        f = fundamentals(s)
        prev = comp.get(s, {})
        if f["mcapCr"] is None:
            f["mcapCr"] = prev.get("mcapCr") or uni.get(s, {}).get("sovrennMcapCr")
        if f["revenueCr"] is None:
            f["revenueCr"], f["revenueBasis"] = prev.get("revenueCr"), prev.get("revenueBasis")
        f["updated"] = today.isoformat()
        comp[s] = f
    cutoff = today - timedelta(days=20)
    for s in syms:
        need = [o for o in all_orders if o["ticker"] == s and (o.get("d5") is None and o["date"] >= (today - timedelta(days=200)).isoformat())]
        if not need:
            continue
        try:
            start = min(o["date"] for o in need)
            h = yf.Ticker(s).history(start=(date.fromisoformat(start) - timedelta(days=10)).isoformat(), auto_adjust=False)
        except Exception:
            h = None
        for o in need:
            o.update(price_reaction(h, datetime.fromisoformat(o["announcedAt"])))
    for o in all_orders:
        f = comp.get(o["ticker"], {})
        o["mcapCr"] = f.get("mcapCr")
        o["revenueCr"] = f.get("revenueCr")
        o["revenueBasis"] = f.get("revenueBasis")
        o["segments"] = uni.get(o["ticker"], {}).get("segments", o.get("segments", []))
        av = o.get("annualValueCr")
        o["orderSizePct"] = round(av / o["revenueCr"] * 100, 2) if av and o.get("revenueCr") else None
        o["pctOfMcap"] = round(o["valueCr"] / o["mcapCr"] * 100, 2) if o.get("valueCr") and o.get("mcapCr") else None

    all_orders.sort(key=lambda o: o["announcedAt"], reverse=True)
    store = {
        "updatedAt": datetime.now(IST).isoformat(timespec="minutes"),
        "windowStart": min([o["date"] for o in all_orders], default=frm.isoformat()),
        "trackedCompanies": len(tracked()),
        "sources": ["NSE corporate announcements", "BSE filings via screener.in"],
        "notes": "Values parsed from exchange filings; 'null' means the filing didn't state it or it couldn't be read. "
                 "Order size % = annual value / company revenue (TTM where available). 1D/3D/5D = % move from the "
                 "last close before the filing.",
        "fx": {"USDINR": round(usdinr, 2), "EURINR": round(eurinr, 2)},
        "companies": comp,
        "orders": all_orders,
    }
    OUT.write_text(json.dumps(store, indent=1, ensure_ascii=False))
    if DOCS_DATA.is_dir():
        (DOCS_DATA / "orders.json").write_text(OUT.read_text())
    Path(a.new_out).write_text(json.dumps({"new": fresh, "errors": errors}, indent=1, ensure_ascii=False))
    print(json.dumps({"newOrders": len(fresh), "totalOrders": len(all_orders), "companiesWithOrders": len(syms),
                      "errors": errors[:30], "errorCount": len(errors)}, indent=1))
    return 0


def build(oid, t, c, ann, head, body, url, source, usdinr, eurinr) -> dict:
    text = f"{head}\n{body}"
    band = classification_range(text)
    val = None if band else (extract_value(head, usdinr, eurinr) or extract_value(body, usdinr, eurinr))
    dur = extract_duration_months(body) or until_months(body, ann.date())
    annual = None
    if val:
        annual = round(val * 12 / dur, 2) if dur and dur > 12 else val
    summ = re.sub(r"\s+", " ", head).strip()
    summ = re.sub(r"^.*?has informed the Exchange (about|regarding)\s*", "", summ, flags=re.I)[:220]
    return {
        "id": oid,
        "ticker": t,
        "symbol": re.sub(r"\.(NS|BO)$", "", t),
        "company": c.get("name"),
        "segments": c["segments"],
        "date": ann.date().isoformat(),
        "announcedAt": ann.isoformat(),
        "customer": extract_customer(body) or extract_customer(head),
        "orderType": extract_type(text),
        "scope": extract_scope(body),
        "valueCr": val,
        "valueBand": band,
        "durationMonths": dur,
        "annualValueCr": annual,
        "summary": summ,
        "pdf": url,
        "source": source,
        "textRead": len(body.strip()) > 200,
        "d1": None, "d3": None, "d5": None,
    }


if __name__ == "__main__":
    sys.exit(main())
