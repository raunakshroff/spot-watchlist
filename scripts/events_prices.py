"""Price / buy-zone refresh + Active promotion for public/data/events.json.

Reuses sovrenn_prices.evaluate (same daily buy-zone rules). Sets priceAtEvent
once (close on/before event date), pctSinceEvent, rsi14, DMAs, buyZone.

Promotion heuristic (conservative — documented for daily chat note):
  Promote an Events company into watchlist.json when ALL of:
    * not already on Active watchlist and not in dropped.json
    * not already flagged promotedToActive
    * AND either:
        (A) buyZone == "Y", OR
        (B) near-breakout bundle:
              - close > dma20 and close > dma50 (uptrend structure)
              - RSI14 in [45, 68]
              - pctSinceEvent >= 2.0
              - close within 3% of the 20-session high
              - not extended: close <= 12% above dma20
  On promote: append Watchlist row with status "Breakout-watch" (or "Watch"
  if only buyZone Y without breakout proximity), levels "—", thesis linking
  to the event, addedDate = today IST, buyZone False unless we have real levels
  (we do not invent levels → buyZone false, buyZoneLevels null).
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sovrenn_prices import _hist, evaluate

IST = ZoneInfo("Asia/Kolkata")


def _price_on_or_before(h, date_str: str):
    idx = [i for i, d in enumerate(h.index.strftime("%Y-%m-%d")) if d <= date_str]
    if not idx:
        return None, None
    i = idx[-1]
    return round(float(h["Close"].iloc[i]), 2), h.index[i].strftime("%Y-%m-%d")


def _near_breakout(h, ev: dict) -> bool:
    """Conservative near-breakout / upward-move check (rule B)."""
    price = ev.get("price")
    d20, d50 = ev.get("dma20"), ev.get("dma50")
    rsi = ev.get("rsi14")
    pct = ev.get("pctSinceEvent")
    if None in (price, d20, d50, rsi, pct):
        return False
    if not (price > d20 and price > d50):
        return False
    if not (45 <= rsi <= 68):
        return False
    if pct < 2.0:
        return False
    if (price / d20 - 1) * 100 > 12:
        return False
    closes = h["Close"].tail(20)
    if len(closes) < 20:
        return False
    hi20 = float(closes.max())
    if hi20 <= 0:
        return False
    # within 3% of 20-session high
    return (hi20 / price - 1) * 100 <= 3.0


def refresh(db: dict) -> None:
    """Mutate events.json object in place with live Yahoo metrics."""
    now = datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
    for ev in db.get("events", []):
        for c in ev.get("companies", []):
            t = c.get("ticker")
            if not t:
                c.update({"price": None, "buyZone": "n/a", "buyZoneNote": "no ticker"})
                continue
            h = _hist(t)
            if h is None or len(h) < 15:
                print(f"WARN events: no data for {t}")
                c.update({"price": None, "buyZone": "n/a", "buyZoneNote": "no price data"})
                continue
            metrics = evaluate(h)
            c.update({
                "price": metrics["price"],
                "priceDate": metrics["priceDate"],
                "dma20": metrics["dma20"],
                "dma50": metrics["dma50"],
                "dma200": metrics["dma200"],
                "rsi14": metrics["rsi14"],
                "buyZone": metrics["buyZone"],
                "buyZoneNote": metrics["buyZoneNote"],
                "lastUpdated": now,
            })
            # Set priceAtEvent once (first successful close on/before event date)
            if c.get("priceAtEvent") is None:
                p0, d0 = _price_on_or_before(h, ev["date"])
                c["priceAtEvent"] = p0
                c["priceAtEventDate"] = d0
            p0 = c.get("priceAtEvent")
            c["pctSinceEvent"] = (
                round((metrics["price"] / p0 - 1) * 100, 2) if p0 and metrics["price"] else None
            )
            c["_hist_ok"] = True  # ephemeral; stripped before save
            c["_nearBreakout"] = _near_breakout(h, c)
            print(
                f"events {t}: {metrics['price']} bz={metrics['buyZone']} "
                f"since={c['pctSinceEvent']} nearBO={c['_nearBreakout']}"
            )
    db["updatedAt"] = datetime.now(IST).strftime("%Y-%m-%d")


def _should_promote(c: dict) -> bool:
    if c.get("promotedToActive"):
        return False
    if c.get("buyZone") == "Y":
        return True
    return bool(c.get("_nearBreakout"))


def promote_to_active(
    db: dict,
    watchlist: list[dict],
    dropped: list[dict],
    day: str,
) -> list[dict]:
    """Append qualifying Events companies to watchlist. Returns promotion records.

    Does NOT bulk-seed: only names that pass the heuristic on a daily run.
    """
    active = {w["ticker"] for w in watchlist}
    dropped_set = {d["ticker"] for d in dropped}
    promotions: list[dict] = []

    for ev in db.get("events", []):
        for c in ev.get("companies", []):
            t = c.get("ticker")
            if not t or t in active or t in dropped_set:
                # If already on Active, mark so we don't re-suggest forever
                if t in active and not c.get("promotedToActive"):
                    c["promotedToActive"] = True
                    c["promotedNote"] = "already on Active watchlist"
                continue
            if not _should_promote(c):
                continue
            status = "Breakout-watch" if c.get("_nearBreakout") else "Watch"
            reason = (
                f"Events auto-promote from {ev['id']}: "
                + (
                    "buy-zone Y"
                    if c.get("buyZone") == "Y"
                    else "near breakout / upward move"
                )
                + f" · {c.get('why', '')[:160]}"
            )
            row = {
                "ticker": t,
                "name": c.get("name") or t.replace(".NS", "").replace(".BO", ""),
                "sector": "Defence / Aerospace",
                "status": status,
                "thesis": reason,
                "buyZone": False,
                "buyZoneLevels": None,
                "stop": None,
                "target1": None,
                "target2": None,
                "price": c.get("price"),
                "dailyPct": None,
                "rsi14": c.get("rsi14"),
                "volume": None,
                "volVs20d": None,
                "support": None,
                "resistance": None,
                "sharesHeld": None,
                "avgCost": None,
                "addedDate": day,
                "lastUpdated": day,
                "notes": f"Promoted from Events · {ev.get('title')} ({ev.get('date')})",
            }
            watchlist.append(row)
            active.add(t)
            c["promotedToActive"] = True
            c["promotedDate"] = day
            c["promotedStatus"] = status
            promotions.append({
                "ticker": t,
                "name": row["name"],
                "status": status,
                "eventId": ev["id"],
                "buyZone": c.get("buyZone"),
                "pctSinceEvent": c.get("pctSinceEvent"),
                "rsi14": c.get("rsi14"),
                "reason": "buy-zone Y" if c.get("buyZone") == "Y" else "near breakout",
            })
            print(f"PROMOTE events→Active: {t} as {status}")

    return promotions


def strip_ephemeral(db: dict) -> None:
    for ev in db.get("events", []):
        for c in ev.get("companies", []):
            c.pop("_hist_ok", None)
            c.pop("_nearBreakout", None)


def format_promotion_note(promotions: list[dict]) -> str:
    if not promotions:
        return "Events→Active: none promoted today."
    bits = [
        f"{p['ticker'].replace('.NS','').replace('.BO','')} ({p['status']}, {p['reason']}"
        + (f", {p['pctSinceEvent']:+.1f}% since event" if p.get("pctSinceEvent") is not None else "")
        + ")"
        for p in promotions
    ]
    return "Events→Active promoted: " + "; ".join(bits)
