"""Render the end-of-day 'new orders' email from orders_ingest.py --new-out output.

Usage: python scripts/orders_email.py /tmp/orders_new.json > /tmp/orders_email.html
Prints nothing (exit 3) when there are no new orders.
"""
import html
import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

SITE = "https://raunakshroff.github.io/spot-watchlist/#orders"


def cr(n):
    return "Not mentioned" if n is None else f"₹{n:,.2f} Cr".replace(".00 Cr", " Cr")


def pct(n):
    return "n/a" if n is None else f"{n:.2f}%"


def main():
    d = json.load(open(sys.argv[1]))
    new = sorted(d.get("new", []), key=lambda o: (o.get("orderSizePct") or -1), reverse=True)
    if not new:
        return 3
    # enrich with computed fields from orders.json (size %, mcap)
    try:
        store = {o["id"]: o for o in json.load(open("public/data/orders.json"))["orders"]}
        new = [store.get(o["id"], o) for o in new]
        new.sort(key=lambda o: (o.get("orderSizePct") or -1), reverse=True)
    except Exception:
        pass
    today = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y")
    rows = []
    for o in new:
        big = (o.get("orderSizePct") or 0) >= 10
        rows.append(
            "<tr>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'><b>{html.escape(o['company'] or o['symbol'])}</b><br>"
            f"<span style='color:#888;font-size:12px'>{o['symbol']} · {' / '.join(o.get('segments', []))}</span></td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{html.escape(o.get('customer') or 'Not mentioned')}<br>"
            f"<span style='color:#888;font-size:12px'>{html.escape(o.get('orderType') or '')}</span></td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right'>{cr(o.get('valueCr'))}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right;{'color:#16a34a;font-weight:bold' if big else ''}'>{pct(o.get('orderSizePct'))}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right'>{pct(o.get('pctOfMcap'))}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'><a href='{html.escape(o['pdf'])}'>Filing</a></td>"
            "</tr>"
        )
    errs = d.get("errors") or []
    note = f"<p style='color:#888;font-size:12px'>{len(errs)} companies couldn't be checked today.</p>" if errs else ""
    print(
        f"<div style='font-family:Arial,sans-serif;font-size:14px;color:#222'>"
        f"<p>{len(new)} new order{'s' if len(new) != 1 else ''} filed by companies you track ({today}).</p>"
        "<table style='border-collapse:collapse;width:100%'><tr style='background:#f5f5f5;text-align:left'>"
        "<th style='padding:8px'>Company</th><th style='padding:8px'>Customer / type</th><th style='padding:8px;text-align:right'>Value</th>"
        "<th style='padding:8px;text-align:right'>% of revenue</th><th style='padding:8px;text-align:right'>% of mcap</th><th style='padding:8px'>PDF</th></tr>"
        + "".join(rows)
        + "</table>"
        f"<p><a href='{SITE}'>Open the Orders dashboard</a></p>{note}"
        "<p style='color:#888;font-size:12px'>Parsed from NSE/BSE filings; check the PDF before acting. Research, not SEBI advice.</p></div>"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
