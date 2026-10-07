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
]

# Not equity sector/market indices -> excluded from the vs-Nifty board
EXCLUDE_NSE_KEYS = {"FIXED INCOME INDICES"}
EXCLUDE_NSE_SYMBOLS = {
    "NIFTY 50",  # benchmark itself
    "INDIA VIX",  # volatility, not a price index
    "NIFTY50 TR 2X LEV",
    "NIFTY50 PR 2X LEV",
    "NIFTY50 TR 1X INV",
    "NIFTY50 PR 1X INV",
    "NIFTY50 DIV POINT",
}

GROUP_BY_NSE_KEY = {
    "BROAD MARKET INDICES": "Broad Market",
    "SECTORAL INDICES": "Sectoral",
    "THEMATIC INDICES": "Thematic",
    "STRATEGY INDICES": "Strategy",
}
# Derivatives-eligible block mixes broad + sectoral; pin these explicitly
GROUP_OVERRIDES = {
    "NIFTY BANK": "Sectoral",
    "NIFTY FIN SERVICE": "Sectoral",
    "NIFTY NEXT 50": "Broad Market",
    "NIFTY MID SELECT": "Broad Market",
    "NIFTY FPI 150": "Broad Market",
}

BSE_INDICES = [
    {"name": "BSE Sensex", "symbol": "^BSESN"},
    {"name": "BSE 100", "symbol": "BSE-100.BO"},
    {"name": "BSE 500", "symbol": "BSE-500.BO"},
]

# NSE indexSymbol -> Yahoo symbol (each verified to return data on 2026-10-07)
YAHOO_SYMBOLS: dict[str, str] = {
    "NIFTY 50": "^NSEI",
    "NIFTY NEXT 50": "^NSMIDCP",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY FIN SERVICE": "NIFTY_FIN_SERVICE.NS",
    "NIFTY MID SELECT": "NIFTY_MID_SELECT.NS",
    "NIFTY FPI 150": "NIFTY_FPI_150.NS",
    "NIFTY 100": "^CNX100",
    "NIFTY 200": "^CNX200",
    "NIFTY 500": "^CRSLDX",
    "NIFTY MIDCAP 50": "^NSEMDCP50",
    "NIFTY MIDCAP 100": "NIFTY_MIDCAP_100.NS",
    "NIFTY SMLCAP 100": "^CNXSC",
    "INDIA VIX": "^INDIAVIX",
    "NIFTY500 MULTICAP": "NIFTY500_MULTICAP.NS",
    "NIFTY LARGEMID250": "NIFTY_LARGEMID250.NS",
    "NIFTY TOTAL MKT": "NIFTY_TOTAL_MKT.NS",
    "NIFTY MICROCAP250": "NIFTY_MICROCAP250.NS",
    "NIFTY500 LMS EQL": "NIFTY500_LMS_EQL.NS",
    "NIFTY SMALLCAP 500": "NIFTY_SMALLCAP_500.NS",
    "NIFTY AUTO": "^CNXAUTO",
    "NIFTY FINSRV25 50": "^CNXFIN",
    "NIFTY FMCG": "^CNXFMCG",
    "NIFTY IT": "^CNXIT",
    "NIFTY MEDIA": "^CNXMEDIA",
    "NIFTY METAL": "^CNXMETAL",
    "NIFTY PHARMA": "^CNXPHARMA",
    "NIFTY PSU BANK": "^CNXPSUBANK",
    "NIFTY PVT BANK": "NIFTY_PVT_BANK.NS",
    "NIFTY REALTY": "^CNXREALTY",
    "NIFTY HEALTHCARE": "NIFTY_HEALTHCARE.NS",
    "NIFTY CONSR DURBL": "NIFTY_CONSR_DURBL.NS",
    "NIFTY OIL AND GAS": "NIFTY_OIL_AND_GAS.NS",
    "NIFTY MIDSML HLTH": "NIFTY_MIDSML_HLTH.NS",
    "NIFTY FINSEREXBNK": "NIFTY_FINSEREXBNK.NS",
    "NIFTY MS FIN SERV": "NIFTY_MS_FIN_SERV.NS",
    "NIFTY MS IT TELCM": "NIFTY_MS_IT_TELCM.NS",
    "NIFTY CHEMICALS": "NIFTY_CHEMICALS.NS",
    "NIFTY500 HEALTH": "NIFTY500_HEALTH.NS",
    "NIFTY REITS REALTY": "NIFTY_REITS_REALTY.NS",
    "NIFTY CEMENT": "NIFTY_CEMENT.NS",
    "NIFTY DIV OPPS 50": "^CNXDIVOP",
    "NIFTY100 EQL WGT": "NIFTY100_EQL_WGT.NS",
    "NIFTY200MOMENTM30": "NIFTY200MOMENTM30.NS",
    "NIFTY M150 QLTY50": "NIFTY_M150_QLTY50.NS",
    "NIFTY200 ALPHA 30": "NIFTY200_ALPHA_30.NS",
    "NIFTYM150MOMNTM50": "NIFTYM150MOMNTM50.NS",
    "NIFTY500MOMENTM50": "NIFTY500MOMENTM50.NS",
    "NIFTYMS400 MQ 100": "NIFTYMS400_MQ_100.NS",
    "NIFTYSML250MQ 100": "NIFTYSML250MQ_100.NS",
    "NIFTY TOP 10 EW": "NIFTY_TOP_10_EW.NS",
    "NIFTY AQL 30": "NIFTY_AQL_30.NS",
    "NIFTY AQLV 30": "NIFTY_AQLV_30.NS",
    "NIFTY HIGHBETA 50": "NIFTY_HIGHBETA_50.NS",
    "NIFTY LOW VOL 50": "NIFTY_LOW_VOL_50.NS",
    "NIFTY QLTY LV 30": "NIFTY_QLTY_LV_30.NS",
    "NIFTY SML250 Q50": "NIFTY_SML250_Q50.NS",
    "NIFTY TOP 15 EW": "NIFTY_TOP_15_EW.NS",
    "NIFTY100 ALPHA 30": "NIFTY100_ALPHA_30.NS",
    "NIFTY200 VALUE 30": "NIFTY200_VALUE_30.NS",
    "NIFTY500 EW": "NIFTY500_EW.NS",
    "NIFTY MULTI MQ 50": "NIFTY_MULTI_MQ_50.NS",
    "NIFTY500 VALUE 50": "NIFTY500_VALUE_50.NS",
    "NIFTY TOP 20 EW": "NIFTY_TOP_20_EW.NS",
    "NIFTY500 QLTY50": "NIFTY500_QLTY50.NS",
    "NIFTY500 LOWVOL50": "NIFTY500_LOWVOL50.NS",
    "NIFTY500 MQVLV50": "NIFTY500_MQVLV50.NS",
    "NIFTY50 USD": "NIFTY50_USD.NS",
    "NIFTY500 FLEXICAP": "NIFTY500_FLEXICAP.NS",
    "NIFTY TMMQ 50": "NIFTY_TMMQ_50.NS",
    "NIFTY COMMODITIES": "^CNXCMDT",
    "NIFTY CONSUMPTION": "^CNXCONSUM",
    "NIFTY CPSE": "NIFTY_CPSE.NS",
    "NIFTY ENERGY": "^CNXENERGY",
    "NIFTY INFRA": "^CNXINFRA",
    "NIFTY MNC": "^CNXMNC",
    "NIFTY PSE": "^CNXPSE",
    "NIFTY SERV SECTOR": "^CNXSERVICE",
    "NIFTY100ESGSECLDR": "NIFTY100ESGSECLDR.NS",
    "NIFTY IND DIGITAL": "NIFTY_IND_DIGITAL.NS",
    "NIFTY100 ESG": "NIFTY100_ESG.NS",
    "NIFTY INDIA MFG": "NIFTY_INDIA_MFG.NS",
    "NIFTY TATA 25 CAP": "NIFTY_TATA_25_CAP.NS",
    "NIFTY MULTI MFG": "NIFTY_MULTI_MFG.NS",
    "NIFTY MULTI INFRA": "NIFTY_MULTI_INFRA.NS",
    "NIFTY IND DEFENCE": "NIFTY_IND_DEFENCE.NS",
    "NIFTY IND TOURISM": "NIFTY_IND_TOURISM.NS",
    "NIFTY CAPITAL MKT": "NIFTY_CAPITAL_MKT.NS",
    "NIFTY EV": "NIFTY_EV.NS",
    "NIFTY NEW CONSUMP": "NIFTY_NEW_CONSUMP.NS",
    "NIFTY CORP MAATR": "NIFTY_CORP_MAATR.NS",
    "NIFTY MOBILITY": "NIFTY_MOBILITY.NS",
    "NIFTY100 ENH ESG": "NIFTY100_ENH_ESG.NS",
    "NIFTY COREHOUSING": "NIFTY_COREHOUSING.NS",
    "NIFTY HOUSING": "NIFTY_HOUSING.NS",
    "NIFTY IPO": "NIFTY_IPO.NS",
    "NIFTY MS IND CONS": "NIFTY_MS_IND_CONS.NS",
    "NIFTY NONCYC CONS": "NIFTY_NONCYC_CONS.NS",
    "NIFTY RURAL": "NIFTY_RURAL.NS",
    "NIFTY SHARIAH 25": "NIFTY_SHARIAH_25.NS",
    "NIFTY TRANS LOGIS": "NIFTY_TRANS_LOGIS.NS",
    "NIFTY50 SHARIAH": "NIFTY50_SHARIAH.NS",
    "NIFTY500 SHARIAH": "NIFTY500_SHARIAH.NS",
    "NIFTY SME EMERGE": "NIFTY_SME_EMERGE.NS",
    "NIFTY INTERNET": "NIFTY_INTERNET.NS",
    "NIFTY WAVES": "NIFTY_WAVES.NS",
    "NIFTY INFRALOG": "NIFTY_INFRALOG.NS",
    "NIFTY RAILWAYSPSU": "NIFTY_RAILWAYSPSU.NS",
    "NIFTYCONGLOMERATE": "NIFTYCONGLOMERATE.NS",
}

# NSE index catalog (indexSymbol, display name, group) — used for Yahoo fallback
INDEX_CATALOG: list[tuple[str, str, str]] = [
    ("NIFTY 100", "Nifty 100", "Broad Market"),
    ("NIFTY 200", "Nifty 200", "Broad Market"),
    ("NIFTY 500", "Nifty 500", "Broad Market"),
    ("NIFTY FPI 150", "Nifty India FPI 150", "Broad Market"),
    ("NIFTY LARGEMID250", "Nifty Largemidcap 250", "Broad Market"),
    ("NIFTY MIDSMALL 50 50", "Nifty Midsmallcap400 50:50", "Broad Market"),
    ("NIFTY MICROCAP250", "Nifty Microcap 250", "Broad Market"),
    ("NIFTY MIDCAP 100", "Nifty Midcap 100", "Broad Market"),
    ("NIFTY MIDCAP 150", "Nifty Midcap 150", "Broad Market"),
    ("NIFTY MIDCAP 50", "Nifty Midcap 50", "Broad Market"),
    ("NIFTY MID SELECT", "Nifty Midcap Select", "Broad Market"),
    ("NIFTY MIDSML 400", "Nifty Midsmallcap 400", "Broad Market"),
    ("NIFTY NEXT 50", "Nifty Next 50", "Broad Market"),
    ("NIFTY SMLCAP 100", "Nifty Smallcap 100", "Broad Market"),
    ("NIFTY SMLCAP 250", "Nifty Smallcap 250", "Broad Market"),
    ("NIFTY SMLCAP 50", "Nifty Smallcap 50", "Broad Market"),
    ("NIFTY SMALLCAP 500", "Nifty Smallcap 500", "Broad Market"),
    ("NIFTY TOTAL MKT", "Nifty Total Market", "Broad Market"),
    ("NIFTY500 LMS EQL", "Nifty500 Largemidsmall Equal-Cap Weighted", "Broad Market"),
    ("NIFTY500 MULTICAP", "Nifty500 Multicap 50:25:25", "Broad Market"),
    ("NIFTY AUTO", "Nifty Auto", "Sectoral"),
    ("NIFTY BANK", "Nifty Bank", "Sectoral"),
    ("NIFTY CEMENT", "Nifty Cement", "Sectoral"),
    ("NIFTY CHEMICALS", "Nifty Chemicals", "Sectoral"),
    ("NIFTY CONSR DURBL", "Nifty Consumer Durables", "Sectoral"),
    ("NIFTY FMCG", "Nifty FMCG", "Sectoral"),
    ("NIFTY FIN SERVICE", "Nifty Financial Services", "Sectoral"),
    ("NIFTY FINSRV25 50", "Nifty Financial Services 25/50", "Sectoral"),
    ("NIFTY FINSEREXBNK", "Nifty Financial Services Ex-Bank", "Sectoral"),
    ("NIFTY HEALTHCARE", "Nifty Healthcare Index", "Sectoral"),
    ("NIFTY IT", "Nifty IT", "Sectoral"),
    ("NIFTY MEDIA", "Nifty Media", "Sectoral"),
    ("NIFTY METAL", "Nifty Metal", "Sectoral"),
    ("NIFTY MS FIN SERV", "Nifty Midsmall Financial Services", "Sectoral"),
    ("NIFTY MIDSML HLTH", "Nifty Midsmall Healthcare", "Sectoral"),
    ("NIFTY MS IT TELCM", "Nifty Midsmall IT & Telecom", "Sectoral"),
    ("NIFTY OIL AND GAS", "Nifty Oil & Gas", "Sectoral"),
    ("NIFTY PSU BANK", "Nifty PSU Bank", "Sectoral"),
    ("NIFTY PHARMA", "Nifty Pharma", "Sectoral"),
    ("NIFTY PVT BANK", "Nifty Private Bank", "Sectoral"),
    ("NIFTY REITS REALTY", "Nifty REITs & Realty", "Sectoral"),
    ("NIFTY REALTY", "Nifty Realty", "Sectoral"),
    ("NIFTY500 HEALTH", "Nifty500 Healthcare", "Sectoral"),
    ("NIFTY CPSE", "Nifty CPSE", "Thematic"),
    ("NIFTY CAPITAL MKT", "Nifty Capital Markets", "Thematic"),
    ("NIFTY COMMODITIES", "Nifty Commodities", "Thematic"),
    ("NIFTYCONGLOMERATE", "Nifty Conglomerate 50", "Thematic"),
    ("NIFTY COREHOUSING", "Nifty Core Housing", "Thematic"),
    ("NIFTY EV", "Nifty EV & New Age Automotive", "Thematic"),
    ("NIFTY ENERGY", "Nifty Energy", "Thematic"),
    ("NIFTY HOUSING", "Nifty Housing", "Thematic"),
    ("NIFTY IPO", "Nifty IPO", "Thematic"),
    ("NIFTY CONSUMPTION", "Nifty India Consumption", "Thematic"),
    ("NIFTY TATA 25 CAP", "Nifty India Corporate Group Index - Tata Group 25% Cap", "Thematic"),
    ("NIFTY IND DEFENCE", "Nifty India Defence", "Thematic"),
    ("NIFTY IND DIGITAL", "Nifty India Digital", "Thematic"),
    ("NIFTY INFRALOG", "Nifty India Infrastructure & Logistics", "Thematic"),
    ("NIFTY INTERNET", "Nifty India Internet", "Thematic"),
    ("NIFTY INDIA MFG", "Nifty India Manufacturing", "Thematic"),
    ("NIFTY NEW CONSUMP", "Nifty India New Age Consumption", "Thematic"),
    ("NIFTY RAILWAYSPSU", "Nifty India Railways PSU", "Thematic"),
    ("NIFTY CORP MAATR", "Nifty India Select 5 Corporate Groups (MAATR)", "Thematic"),
    ("NIFTY IND TOURISM", "Nifty India Tourism", "Thematic"),
    ("NIFTY INFRA", "Nifty Infrastructure", "Thematic"),
    ("NIFTY MNC", "Nifty MNC", "Thematic"),
    ("NIFTY MID LIQ 15", "Nifty Midcap Liquid 15", "Thematic"),
    ("NIFTY MS IND CONS", "Nifty Midsmall India Consumption", "Thematic"),
    ("NIFTY MOBILITY", "Nifty Mobility", "Thematic"),
    ("NIFTY NONCYC CONS", "Nifty Non-Cyclical Consumer", "Thematic"),
    ("NIFTY PSE", "Nifty PSE", "Thematic"),
    ("NIFTY RURAL", "Nifty Rural", "Thematic"),
    ("NIFTY SME EMERGE", "Nifty SME Emerge", "Thematic"),
    ("NIFTY SERV SECTOR", "Nifty Services Sector", "Thematic"),
    ("NIFTY SHARIAH 25", "Nifty Shariah 25", "Thematic"),
    ("NIFTY TRANS LOGIS", "Nifty Transportation & Logistics", "Thematic"),
    ("NIFTY WAVES", "Nifty Waves", "Thematic"),
    ("NIFTY100 ESG", "Nifty100 ESG", "Thematic"),
    ("NIFTY100ESGSECLDR", "Nifty100 ESG Sector Leaders", "Thematic"),
    ("NIFTY100 ENH ESG", "Nifty100 Enhanced ESG", "Thematic"),
    ("NIFTY100 LIQ 15", "Nifty100 Liquid 15", "Thematic"),
    ("NIFTY50 SHARIAH", "Nifty50 Shariah", "Thematic"),
    ("NIFTY MULTI MFG", "Nifty500 Multicap India Manufacturing 50:30:20", "Thematic"),
    ("NIFTY MULTI INFRA", "Nifty500 Multicap Infrastructure 50:30:20", "Thematic"),
    ("NIFTY500 SHARIAH", "Nifty500 Shariah", "Thematic"),
    ("NIFTY ALPHA 50", "Nifty Alpha 50", "Strategy"),
    ("NIFTY ALPHALOWVOL", "Nifty Alpha Low-Volatility 30", "Strategy"),
    ("NIFTY AQL 30", "Nifty Alpha Quality Low-Volatility 30", "Strategy"),
    ("NIFTY AQLV 30", "Nifty Alpha Quality Value Low-Volatility 30", "Strategy"),
    ("NIFTY DIV OPPS 50", "Nifty Dividend Opportunities 50", "Strategy"),
    ("NIFTY GROWSECT 15", "Nifty Growth Sectors 15", "Strategy"),
    ("NIFTY HIGHBETA 50", "Nifty High Beta 50", "Strategy"),
    ("NIFTY LOW VOL 50", "Nifty Low Volatility 50", "Strategy"),
    ("NIFTYM150MOMNTM50", "Nifty Midcap150 Momentum 50", "Strategy"),
    ("NIFTY M150 QLTY50", "Nifty Midcap150 Quality 50", "Strategy"),
    ("NIFTYMS400 MQ 100", "Nifty Midsmallcap400 Momentum Quality 100", "Strategy"),
    ("NIFTY QLTY LV 30", "Nifty Quality Low-Volatility 30", "Strategy"),
    ("NIFTYSML250MQ 100", "Nifty Smallcap250 Momentum Quality 100", "Strategy"),
    ("NIFTY SML250 Q50", "Nifty Smallcap250 Quality 50", "Strategy"),
    ("NIFTY TOP 10 EW", "Nifty Top 10 Equal Weight", "Strategy"),
    ("NIFTY TOP 15 EW", "Nifty Top 15 Equal Weight", "Strategy"),
    ("NIFTY TOP 20 EW", "Nifty Top 20 Equal Weight", "Strategy"),
    ("NIFTY TMMQ 50", "Nifty Total Market Momentum Quality 50", "Strategy"),
    ("NIFTY100 ALPHA 30", "Nifty100 Alpha 30", "Strategy"),
    ("NIFTY100 EQL WGT", "Nifty100 Equal Weight", "Strategy"),
    ("NIFTY100 LOWVOL30", "Nifty100 Low Volatility 30", "Strategy"),
    ("NIFTY100 QUALTY30", "Nifty100 Quality 30", "Strategy"),
    ("NIFTY200 ALPHA 30", "Nifty200 Alpha 30", "Strategy"),
    ("NIFTY200MOMENTM30", "Nifty200 Momentum 30", "Strategy"),
    ("NIFTY200 QUALTY30", "Nifty200 Quality 30", "Strategy"),
    ("NIFTY200 VALUE 30", "Nifty200 Value 30", "Strategy"),
    ("NIFTY50 EQL WGT", "Nifty50 Equal Weight", "Strategy"),
    ("NIFTY50 USD", "Nifty50 USD", "Strategy"),
    ("NIFTY50 VALUE 20", "Nifty50 Value 20", "Strategy"),
    ("NIFTY500 EW", "Nifty500 Equal Weight", "Strategy"),
    ("NIFTY500 FLEXICAP", "Nifty500 Flexicap Quality 30", "Strategy"),
    ("NIFTY500 LOWVOL50", "Nifty500 Low Volatility 50", "Strategy"),
    ("NIFTY500MOMENTM50", "Nifty500 Momentum 50", "Strategy"),
    ("NIFTY MULTI MQ 50", "Nifty500 Multicap Momentum Quality 50", "Strategy"),
    ("NIFTY500 MQVLV50", "Nifty500 Multifactor MQVLV 50", "Strategy"),
    ("NIFTY500 QLTY50", "Nifty500 Quality 50", "Strategy"),
    ("NIFTY500 VALUE 50", "Nifty500 Value 50", "Strategy"),
]
GROUP_ORDER = ["Broad Market", "Sectoral", "Thematic", "Strategy", "BSE"]

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
    """Benchmark + every available index with daily/weekly returns."""
    nse = fetch_nse_all_indices()
    rows: list[dict] = []
    skipped: list[dict] = []
    benchmark = None
    data_date = as_of
    week_ref = None

    if nse:
        data_date = parse_nse_date(nse.get("timestamp")) or as_of
        week_ref = parse_nse_date((nse.get("dates") or {}).get("oneWeekAgo"))
        seen: set[str] = set()
        for x in nse["data"]:
            sym = (x.get("indexSymbol") or x.get("index") or "").strip()
            key = (x.get("key") or "").strip()
            if not sym or sym in seen:
                continue
            seen.add(sym)
            last = num(x.get("last"))
            daily = num(x.get("percentChange"))
            wk = num(x.get("oneWeekAgoVal"))
            weekly = pct(last, wk) if last and wk else None
            if sym == BENCHMARK_NSE:
                benchmark = {
                    "name": "Nifty 50",
                    "symbol": "^NSEI",
                    "nseSymbol": sym,
                    "last": round(last, 2) if last else None,
                    "dailyPct": round(daily, 2) if daily is not None else None,
                    "weeklyPct": weekly,
                    "source": "official",
                    "dataSource": "nse",
                }
                continue
            if key in EXCLUDE_NSE_KEYS or sym in EXCLUDE_NSE_SYMBOLS:
                skipped.append({"nseSymbol": sym, "reason": "excluded (not an equity index / benchmark variant)"})
                continue
            if last is None or daily is None:
                skipped.append({"nseSymbol": sym, "reason": "no data from NSE"})
                continue
            group = GROUP_OVERRIDES.get(sym) or GROUP_BY_NSE_KEY.get(key, "Broad Market")
            rows.append(
                {
                    "id": sym,
                    "name": nice_index_name(x.get("index") or sym),
                    "nseSymbol": sym,
                    "yahooSymbol": YAHOO_SYMBOLS.get(sym),
                    "group": group,
                    "dataSource": "nse",
                    "last": round(last, 2),
                    "dailyPct": round(daily, 2),
                    "weeklyPct": weekly,
                }
            )
        print(f"NSE allIndices: {len(rows)} indices (+benchmark), {len(skipped)} excluded")
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
        for sym, name, group in INDEX_CATALOG:
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
                "group": "BSE",
                "dataSource": "yahoo",
                **r,
            }
        )

    for r in rows:
        r["vsNiftyDaily"] = spread(r["dailyPct"], benchmark["dailyPct"])
        r["vsNiftyWeekly"] = spread(r["weeklyPct"], benchmark["weeklyPct"])

    rows.sort(key=lambda r: (GROUP_ORDER.index(r["group"]) if r["group"] in GROUP_ORDER else 99, r["name"]))
    return {
        "benchmark": benchmark,
        "indices": rows,
        "skipped": skipped,
        "dataDate": data_date,
        "weekRefDate": week_ref,
        "primarySource": "nse" if nse else "yahoo",
    }


def build_indices(watchlist: list[dict], as_of: str) -> dict | None:
    uni = build_index_universe(as_of)
    if not uni:
        return None
    benchmark = uni["benchmark"]
    by_nse = {r["nseSymbol"]: r for r in uni["indices"] if r.get("nseSymbol")}

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
        "disclaimer": (
            "Research / personal tracking only — not investment advice. "
            f"Index levels from {src_txt}; BSE indices via Yahoo Finance. "
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
