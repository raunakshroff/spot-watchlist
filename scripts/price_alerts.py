"""Price alerts on watchlist entries.

Each watchlist entry may carry an optional ``alerts`` list:

    {"id": "igil-pullback-381-386", "type": "range", "low": 381, "high": 386,
     "label": "Pullback entry zone 381–386", "status": "armed", "createdDate": "2026-10-29"}
    {"id": "igil-breakout-419", "type": "closeAbove", "level": 419, ...}
    {"type": "closeBelow", "level": 368, ...}

Trigger rules (evaluated once per day on the completed daily bar, in daily_update.py):
  range       day low <= high and day high >= low  (price traded inside the band)
  closeAbove  day close >  level
  closeBelow  day close <  level

A triggered alert is stamped with triggeredDate / triggeredPrice (the close) / dayLow /
dayHigh / volVs20d, flips to status "triggered", stays in the file, and never re-fires.
Unknown keys on alerts are preserved.

CLI (dry run, never writes):  python scripts/price_alerts.py [TICKER ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _hit(alert: dict, ohlc: dict) -> bool:
    t = alert.get("type")
    lo, hi, close = ohlc.get("low"), ohlc.get("high"), ohlc.get("close")
    if t == "range":
        a, b = alert.get("low"), alert.get("high")
        if None in (a, b, lo, hi):
            return False
        return lo <= b and hi >= a
    if t == "closeAbove":
        return close is not None and alert.get("level") is not None and close > alert["level"]
    if t == "closeBelow":
        return close is not None and alert.get("level") is not None and close < alert["level"]
    return False


def evaluate_stock(stock: dict, ohlc: dict | None, day: str) -> list[dict]:
    """Mutates armed alerts on ``stock`` that fire on ``ohlc``; returns hit records."""
    hits: list[dict] = []
    if not ohlc or ohlc.get("date") != day:
        return hits  # no bar for today (holiday / stale data) -> don't evaluate
    for a in stock.get("alerts") or []:
        if a.get("status", "armed") != "armed" or not _hit(a, ohlc):
            continue
        a["status"] = "triggered"
        a["triggeredDate"] = day
        a["triggeredPrice"] = ohlc.get("close")
        a["dayLow"] = ohlc.get("low")
        a["dayHigh"] = ohlc.get("high")
        a["volVs20d"] = stock.get("volVs20d")
        hits.append({"ticker": stock["ticker"], "name": stock.get("name"), "alert": a})
    return hits


def describe(a: dict) -> str:
    t = a.get("type")
    if t == "range":
        return f"range {a.get('low')}–{a.get('high')}"
    if t == "closeAbove":
        return f"close > {a.get('level')}"
    if t == "closeBelow":
        return f"close < {a.get('level')}"
    return str(t)


def armed_count(watchlist: list[dict]) -> int:
    return sum(1 for s in watchlist for a in (s.get("alerts") or []) if a.get("status", "armed") == "armed")


def format_note(hits: list[dict], watchlist: list[dict]) -> str:
    armed = armed_count(watchlist)
    if not hits:
        return f"Price alerts triggered: none · armed alerts: {armed}"
    lines = [f"Price alerts triggered ({len(hits)}) · armed alerts remaining: {armed}"]
    for h in hits:
        a = h["alert"]
        tk = h["ticker"].replace(".NS", "").replace(".BO", "")
        vol = a.get("volVs20d")
        vol_s = f", vol {vol:.2f}x 20d" if isinstance(vol, (int, float)) else ""
        lines.append(
            f"- {tk}: {a.get('label') or describe(a)} — close ₹{a.get('triggeredPrice')} "
            f"(day L {a.get('dayLow')} / H {a.get('dayHigh')}{vol_s})"
        )
    return "\n".join(lines)


def _cli(argv: list[str]) -> int:
    sys.path.insert(0, str(Path(__file__).parent))
    from daily_update import DATA, fetch_metrics  # noqa: E402

    wl = json.loads((DATA / "watchlist.json").read_text(encoding="utf-8"))
    want = {t.upper() for t in argv}
    for s in wl:
        if not s.get("alerts") or (want and s["ticker"].upper() not in want):
            continue
        m = fetch_metrics(s["ticker"]) or {}
        ohlc = m.get("ohlc")
        print(f"{s['ticker']} bar: {ohlc}")
        for a in s["alerts"]:
            st = a.get("status", "armed")
            fire = bool(ohlc) and st == "armed" and _hit(a, ohlc)
            print(f"  [{st}] {a.get('label') or describe(a)} -> {'WOULD TRIGGER' if fire else 'no trigger'}")
    print("(dry run — nothing written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
