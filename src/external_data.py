"""
External market indices — live fetch only, never fabricated.

Exactly three data routes, each proven reachable from the plant network:

    Yahoo Finance   Indian indices (Nifty family, Sensex), dry-bulk
                    freight proxy, S&P GSCI
    World Bank      the Commodity 'Pink Sheet' workbook — iron ore, coal,
                    Brent, gas, aluminium, copper, nickel, zinc in one file
    Frankfurter/ECB USD / INR

Every pull is cached under data/external_cache/ and labelled with its
age; a hard time budget keeps the page rendering in seconds; a circuit
breaker with 24-hour memory skips any host that goes dark, with the
exact error preserved in the series status. The one thing this module
never does is invent a number.
"""

from __future__ import annotations

import io
import time
import urllib3
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).resolve().parents[1] / "data" / "external_cache"
CACHE.mkdir(parents=True, exist_ok=True)

YAHOO_SERIES = {          # fetched first — cheap calls, the Indian focus
    "Nifty Metal (NSE)": ["^CNXMETAL"],
    "Nifty Commodities (NSE)": ["^CNXCMDT"],
    "Nifty Energy (NSE)": ["^CNXENERGY"],
    "Nifty Infrastructure (NSE)": ["^CNXINFRA"],
    "Nifty 50": ["^NSEI"],
    "BSE Sensex": ["^BSESN"],
    "Dry-bulk freight (BDRY proxy)": ["BDRY"],
    "S&P GSCI commodity index": ["^SPGSCI"],
}

WB_URL = ("https://thedocs.worldbank.org/en/doc/"
          "5d903e848db1d1b83e0ec8f744e55570-0350012021/related/"
          "CMO-Historical-Data-Monthly.xlsx")
WB_MAP = {
    "iron ore": "Iron ore (global, USD/dmt)",
    "coal, australian": "Coal, Australia (USD/mt)",
    "crude oil, brent": "Crude oil, Brent (USD/bbl)",
    "natural gas, europe": "Natural gas, EU (USD/mmbtu)",
    "aluminum": "Aluminium (USD/mt)",
    "copper": "Copper (USD/mt)",
    "nickel": "Nickel (USD/mt)",
    "zinc": "Zinc (USD/mt)",
}

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36"),
    "Accept": "text/csv,application/json,text/plain,*/*",
}
BREAK = 2


def _session(insecure: bool, proxy: str | None = None):
    import requests
    s = requests.Session()               # trust_env: honours HTTPS_PROXY
    s.headers.update(HEADERS)
    s.verify = not insecure
    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})
    if insecure:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    return s


# ------------------------------------------------------------- the 3 fetchers
def _fetch_yahoo_chart(symbol: str, insecure: bool, proxy: str | None,
                       timeout=(4, 10)):
    from urllib.parse import quote
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{quote(symbol)}?range=10y&interval=1mo")
    try:
        r = _session(insecure, proxy).get(url, timeout=timeout)
        j = r.json()
        res = j["chart"]["result"][0]
        s = pd.Series(res["indicators"]["quote"][0]["close"],
                      index=pd.to_datetime(res["timestamp"],
                                           unit="s")).dropna()
        s.index = s.index.tz_localize(None)
        return (s, None) if len(s) > 12 else (None, "too few points")
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:80]}"


def _fetch_wb_pinksheet(insecure: bool, proxy: str | None,
                        timeout=(5, 15)) -> tuple[dict, str | None]:
    try:
        r = _session(insecure, proxy).get(WB_URL, timeout=timeout)
    except Exception as e:
        return {}, f"{type(e).__name__}: {str(e)[:90]}"
    if r.status_code != 200:
        return {}, f"HTTP {r.status_code}"
    try:
        raw = pd.read_excel(io.BytesIO(r.content),
                            sheet_name="Monthly Prices", header=None)
        best_hdr, best_hits = None, 0
        for i in range(min(15, len(raw))):
            row = " | ".join(str(x).lower() for x in raw.iloc[i].tolist())
            hits = sum(1 for frag in WB_MAP if frag in row)
            if hits > best_hits:
                best_hdr, best_hits = i, hits
        if best_hdr is None or best_hits < 4:
            return {}, "layout not recognised"
        names = raw.iloc[best_hdr].astype(str)
        import re as _re
        start = None
        for i in range(best_hdr + 1, min(best_hdr + 8, len(raw))):
            if _re.fullmatch(r"\d{4}M\d{2}", str(raw.iloc[i, 0]).strip()):
                start = i
                break
        if start is None:
            return {}, "no monthly rows found"
        data = raw.iloc[start:].reset_index(drop=True)
        dates = pd.to_datetime(
            data.iloc[:, 0].astype(str).str.replace("M", "-", regex=False),
            format="%Y-%m", errors="coerce")
        out = {}
        for j, nm in enumerate(names):
            key = str(nm).strip().lower()
            for frag, concept in WB_MAP.items():
                if frag in key and concept not in out:
                    vals = pd.to_numeric(data.iloc[:, j], errors="coerce")
                    s = pd.Series(vals.values, index=dates).dropna()
                    if len(s) > 24:
                        out[concept] = s
        return out, None if out else "no mapped columns found"
    except Exception as e:
        return {}, f"parse {type(e).__name__}: {str(e)[:80]}"


def _fetch_frankfurter_inr(insecure: bool, proxy: str | None,
                           timeout=(4, 12)):
    url = "https://api.frankfurter.app/2015-01-01..?from=USD&to=INR"
    try:
        r = _session(insecure, proxy).get(url, timeout=timeout)
        j = r.json()
        rows = [(pd.Timestamp(d), v["INR"]) for d, v in j["rates"].items()]
        s = pd.Series(dict(rows)).sort_index()
        return (s, None) if len(s) > 12 else (None, "too few points")
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:80]}"


# ------------------------------------------------------------------- caching
def _cache_path(name: str) -> Path:
    safe = "".join(ch if ch.isalnum() else "_" for ch in name)[:60]
    return CACHE / f"{safe}.csv"


def _read_cache(name: str):
    p = _cache_path(name)
    if not p.exists():
        return None, None
    try:
        s = pd.read_csv(p, parse_dates=["date"]).set_index("date")["value"]
        return s, (time.time() - p.stat().st_mtime) / 3600
    except Exception:
        return None, None


def _write_cache(name: str, s: pd.Series):
    s.rename("value").rename_axis("date").reset_index() \
        .to_csv(_cache_path(name), index=False)


def _marker(srcname: str) -> Path:
    return CACHE / f"_blocked_{srcname.lower()}"


def reset_circuit() -> None:
    for p in CACHE.glob("_blocked_*"):
        p.unlink(missing_ok=True)


# ---------------------------------------------------------------- main loader
def load_external(max_age_hours: float = 24.0, insecure: bool = False,
                  budget_s: float = 25.0,
                  proxy: str | None = None) -> tuple[pd.DataFrame, dict]:
    """Returns (wide monthly frame, status per series). Status values:
    'live (SOURCE)', 'cache (Nh old)', 'stale cache (Nh) — last error: …',
    'skipped (time budget)…', or 'unavailable — ERROR'."""
    frames, status = {}, {}
    fails = {"YAHOO": 0, "WB": 0, "FRANK": 0}
    for k in fails:
        m = _marker(k)
        if m.exists() and (time.time() - m.stat().st_mtime) < 24 * 3600:
            fails[k] = BREAK

    def note(srcname, ok):
        if ok:
            fails[srcname] = 0
            _marker(srcname).unlink(missing_ok=True)
        else:
            fails[srcname] += 1
            if fails[srcname] >= BREAK:
                _marker(srcname).touch()

    t0 = time.time()

    def left():
        return budget_s - (time.time() - t0)

    def settle(name, cached, age, errs):
        last = " | ".join(errs) if errs else "skipped"
        if cached is not None:
            frames[name] = cached
            status[name] = f"stale cache ({age:.0f}h) — last error: {last}"
        else:
            status[name] = f"unavailable — {last}"

    # ---- route 1: Yahoo (Indian family + freight + GSCI), fetched first
    for name, symbols in YAHOO_SERIES.items():
        cached, age = _read_cache(name)
        if cached is not None and age is not None and age <= max_age_hours:
            frames[name], status[name] = cached, f"cache ({age:.0f}h old)"
            continue
        errs = []
        for sym in symbols:
            if fails["YAHOO"] >= BREAK:
                errs.append("Yahoo skipped (blocked on this network — "
                            "retested daily or on Refresh)")
                break
            if left() <= 4:
                errs.append("skipped (time budget) — press Refresh")
                break
            got, err = _fetch_yahoo_chart(
                sym, insecure, proxy,
                timeout=(3, max(4, min(9, left() - 1))))
            note("YAHOO", got is not None)
            if got is not None:
                _write_cache(name, got)
                frames[name] = got
                status[name] = f"live (Yahoo {sym})"
                break
            errs.append(f"Yahoo {sym}: {err}")
        if name not in frames:
            settle(name, cached, age, errs)

    # ---- route 2: World Bank Pink Sheet (one download, eight concepts)
    wb_needed = [n for n in WB_MAP.values()
                 if _read_cache(n)[1] is None
                 or _read_cache(n)[1] > max_age_hours]
    wb_data, wb_err = {}, None
    if wb_needed and fails["WB"] < BREAK and left() > 8:
        wb_data, wb_err = _fetch_wb_pinksheet(
            insecure, proxy, timeout=(4, max(6, min(15, left() - 2))))
        note("WB", bool(wb_data))
    for name in WB_MAP.values():
        if name in frames:
            continue
        cached, age = _read_cache(name)
        if cached is not None and age is not None and age <= max_age_hours:
            frames[name], status[name] = cached, f"cache ({age:.0f}h old)"
        elif name in wb_data:
            _write_cache(name, wb_data[name])
            frames[name] = wb_data[name]
            status[name] = "live (World Bank Pink Sheet)"
        else:
            errs = []
            if wb_err:
                errs.append(f"World Bank: {wb_err}")
            elif fails["WB"] >= BREAK:
                errs.append("World Bank skipped (blocked on this network)")
            else:
                errs.append("skipped (time budget) — press Refresh")
            settle(name, cached, age, errs)

    # ---- route 3: Frankfurter/ECB for USD/INR
    name = "USD / INR"
    cached, age = _read_cache(name)
    if cached is not None and age is not None and age <= max_age_hours:
        frames[name], status[name] = cached, f"cache ({age:.0f}h old)"
    elif fails["FRANK"] < BREAK and left() > 4:
        got, err = _fetch_frankfurter_inr(
            insecure, proxy, timeout=(3, max(4, min(10, left() - 1))))
        note("FRANK", got is not None)
        if got is not None:
            _write_cache(name, got)
            frames[name] = got
            status[name] = "live (Frankfurter/ECB)"
        else:
            settle(name, cached, age, [f"Frankfurter: {err}"])
    else:
        settle(name, cached, age,
               ["Frankfurter skipped (blocked or time budget)"])

    if not frames:
        return pd.DataFrame(), status
    wide = pd.DataFrame({k: v.resample("MS").mean()
                         for k, v in frames.items()})
    return wide.dropna(how="all"), status


def connectivity_probe(insecure: bool = False,
                       proxy: str | None = None) -> list[dict]:
    routes = [
        ("Yahoo Finance (query1.finance.yahoo.com)",
         lambda: _fetch_yahoo_chart("^NSEI", insecure, proxy,
                                    timeout=(4, 8))),
        ("World Bank (thedocs.worldbank.org)",
         lambda: ((lambda d, e: (d.get("Copper (USD/mt)"), e))(
             *_fetch_wb_pinksheet(insecure, proxy, timeout=(4, 12))))),
        ("Frankfurter/ECB (api.frankfurter.app)",
         lambda: _fetch_frankfurter_inr(insecure, proxy, timeout=(4, 8))),
    ]
    out = []
    for name, fn in routes:
        t0 = time.time()
        try:
            s, err = fn()
        except Exception as e:
            s, err = None, f"{type(e).__name__}: {str(e)[:80]}"
        out.append(dict(route=name, ok=s is not None,
                        points=int(len(s)) if s is not None else 0,
                        error=err, seconds=round(time.time() - t0, 1)))
    return out


# ==================================================== index -> commodity mapping
INDEX_MAP = [
    dict(index="Nifty Metal (NSE)", region="in",
         patterns=["FERRO", "SILICO", "ELECTRODE", "COKE", "CPC", "SCRAP",
                   "MOULD"],
         how="The domestic barometer: it aggregates Indian steel and mining "
             "producers (Tata Steel, JSW, SAIL, Hindalco, Vedanta, NMDC, "
             "Coal India). A sustained rally signals expected steel demand "
             "and producer pricing power — ferro alloys, electrodes and "
             "carbon inputs typically firm with a 1–3 month lead; a slump "
             "is the negotiating window."),
    dict(index="Nifty Commodities (NSE)", region="in",
         patterns=["FERRO", "SILICO", "ELECTRODE", "BRICK", "CASTABLE",
                   "LIME", "COKE"],
         how="A broad Indian input-cost basket — metals, cement, power, "
             "chemicals. When it inflates, the whole domestic supplier "
             "base faces the same cost push and quotes harden across the "
             "consumables basket."),
    dict(index="Nifty Energy (NSE)", region="in",
         patterns=["SILICO MANGANESE", "FERRO SILICON", "FERRO MANGANESE",
                   "FERRO CHROME", "CALCIUM CARBIDE", "ELECTRODE", "BRICK",
                   "CASTABLE", "LIME"],
         how="Indian power and fuel producers. Ferro-alloy smelting is "
             "electricity in solid form and refractories are kiln-fired — "
             "a domestic energy-cost upcycle reaches their prices within a "
             "quarter or two."),
    dict(index="Nifty 50", region="in",
         patterns=["FERRO", "SILICO", "ELECTRODE", "ROLL", "MOULD"],
         how="The demand-side pulse of the Indian economy. Unlike the cost "
             "benchmarks, this works through demand: a strong market "
             "signals construction/auto/capex momentum → mill utilisation "
             "→ faster consumable drawdown and firmer supplier order books "
             "— pressure on both timing and price."),
    dict(index="BSE Sensex", region="in",
         patterns=["FERRO", "SILICO", "ELECTRODE", "ROLL", "MOULD"],
         how="Same demand-side read as Nifty 50 from the BSE lens; the two "
             "move nearly together, so persistent divergence itself is a "
             "signal worth a second look."),
    dict(index="Nifty Infrastructure (NSE)", region="in",
         patterns=["FERRO", "SILICO", "ELECTRODE", "BRICK"],
         how="Infrastructure order books are long-products steel demand in "
             "waiting — an infra upcycle tightens alloy and consumable "
             "supply with a lag of one to two quarters."),
    dict(index="Dry-bulk freight (BDRY proxy)", region="global",
         patterns=["FERRO", "SILICO", "COKE", "CPC", "COAL", "ALUMINIUM",
                   "NICKEL"],
         how="Ocean freight for ores, coal and alloys — proxied by the "
             "BDRY dry-bulk shipping ETF since the Baltic Dry Index has no "
             "free feed. Freight is a real slice of every imported "
             "commodity's landed cost, and it moves violently: a freight "
             "spike raises landed prices within one or two months even "
             "when the commodity itself is flat."),
    dict(index="S&P GSCI commodity index", region="global",
         patterns=["FERRO", "SILICO", "ELECTRODE", "COKE", "BRICK",
                   "CASTABLE", "LIME"],
         how="The broadest global commodity dial (energy-heavy). Sustained "
             "moves mark cost-inflation regimes across the whole supplier "
             "base — useful context for multi-quarter rate contracts."),
    dict(index="Iron ore (global, USD/dmt)", region="global",
         patterns=["SINTER", "PELLET", "IRON ORE", "DRI", "SCRAP"],
         how="Iron ore is the steelmaking feedstock benchmark; when it "
             "moves, the whole ferrous complex — and freight into it — "
             "usually follows within a quarter."),
    dict(index="Coal, Australia (USD/mt)", region="global",
         patterns=["COKE", "COAL", "CPC", "CARBURIS", "CARBON",
                   "ELECTRODE PASTE"],
         how="Australian coal is the global coking/thermal benchmark; coke, "
             "carbon additives and electrode paste ride its cycles because "
             "coal is their principal cost."),
    dict(index="Crude oil, Brent (USD/bbl)", region="global",
         patterns=["PETROLEUM COKE", "CPC", "LUBRICANT", "OIL", "GREASE",
                   "BITUMEN", "DIESEL"],
         how="Calcined petroleum coke, lubricants and greases are refinery "
             "products — crude sets their raw-material floor, plus every "
             "freight bill in between."),
    dict(index="Natural gas, EU (USD/mmbtu)", region="global",
         patterns=["BRICK", "CASTABLE", "REFRACTOR", "LINING", "MORTAR",
                   "RAMMING", "LIME", "DOLOMITE"],
         how="Refractories, lime and dolomite are kiln-fired products — "
             "fuel is a large slice of their cost, so sustained gas/energy "
             "moves pass into their prices with a lag."),
    dict(index="USD / INR", region="global",
         patterns=["FERRO VANADIUM", "FERRO MOLY", "MOLYBDENUM",
                   "GRAPHITE ELECTRODE", "NICKEL", "FERRO NIOBIUM",
                   "FERRO TITANIUM", "IMPORTED"],
         how="Import-linked alloys and electrodes are dollar-priced "
             "upstream; a weaker rupee raises their landed cost almost "
             "one-for-one even when the dollar price is flat."),
    dict(index="Aluminium (USD/mt)", region="global",
         patterns=["ALUMINIUM", "ALUMINUM", "AL WIRE", "AL INGOT",
                   "AL SHOT", "DEOX"],
         how="Deoxidiser aluminium (notch bars, shots, wire) tracks the LME "
             "aluminium price directly — it is the same metal in a "
             "different shape."),
    dict(index="Copper (USD/mt)", region="global",
         patterns=["COPPER", ",CU", "CU,", "CABLE", "WIRE,WINDING",
                   "MOULD", "BUSBAR", "MOTOR"],
         how="Cables, winding wires, moulds and motor components are "
             "copper-intensive; LME copper is their dominant raw-material "
             "driver."),
    dict(index="Nickel (USD/mt)", region="global",
         patterns=["NICKEL", "FERRO NICKEL", "STAINLESS", "INCONEL",
                   "ELECTRODE,SS", ",SS,"],
         how="Nickel drives stainless and nickel-alloy consumables — "
             "welding electrodes, SS fittings and alloy spares move with "
             "the LME nickel price."),
    dict(index="Zinc (USD/mt)", region="global",
         patterns=["ZINC", "GALVAN", "GI ", "G.I."],
         how="Galvanised items and zinc anodes carry a direct LME-zinc "
             "content cost."),
]


def map_indices_to_commodities(catalog: pd.DataFrame,
                               external: pd.DataFrame | None = None,
                               monthly: pd.DataFrame | None = None,
                               max_lag: int = 3,
                               min_overlap: int = 18) -> list[dict]:
    """For each benchmark: the plant commodities it plausibly touches
    (name-pattern knowledge layer, with the mechanism), plus — when live
    index data and price history are supplied — the measured monthly
    correlation at the best lead (lag 0–3 months), on returns where
    purchase months are dense enough, on levels otherwise."""
    names = catalog["commodity"].tolist()
    spend = catalog.set_index("commodity")["total_spend"].to_dict()
    out = []
    for m in INDEX_MAP:
        pats = [p.upper() for p in m["patterns"]]
        matched = [n for n in names if any(p in n for p in pats)]
        matched.sort(key=lambda n: -spend.get(n, 0))
        measured = []
        if external is not None and monthly is not None \
                and m["index"] in getattr(external, "columns", []):
            lx = np.log(external[m["index"]])
            rx = lx.diff()
            for com in matched[:8]:
                obs = monthly[(monthly["commodity"] == com)
                              & monthly["observed"]]
                s = obs.set_index("month")["price"].resample("MS").last()
                ly = np.log(s)
                ry = ly.diff()
                best = None
                for k in range(max_lag + 1):
                    a, b = ry.align(rx.shift(k), join="inner")
                    ok = a.notna() & b.notna()
                    if ok.sum() >= 12:
                        r = float(a[ok].corr(b[ok]))
                        if best is None or abs(r) > abs(best["rho"]):
                            best = dict(rho=r, lag=k, kind="returns",
                                        n=int(ok.sum()))
                if best is None:
                    for k in range(max_lag + 1):
                        a, b = ly.align(lx.shift(k), join="inner")
                        ok = a.notna() & b.notna()
                        if ok.sum() >= 12:
                            r = float(a[ok].corr(b[ok]))
                            if best is None or abs(r) > abs(best["rho"]):
                                best = dict(rho=r, lag=k, kind="levels",
                                            n=int(ok.sum()))
                if best is not None:
                    measured.append(dict(commodity=com, **best))
            measured.sort(key=lambda d: -abs(d["rho"]))
        out.append(dict(index=m["index"],
                        region=m.get("region", "global"), how=m["how"],
                        matched=matched, n_matched=len(matched),
                        measured=measured))
    return out


def correlate(commodity_obs: pd.DataFrame, external: pd.DataFrame,
              max_lag: int = 3, min_overlap: int = 12) -> pd.DataFrame:
    """Pearson correlation of monthly log-returns, index leading by
    0..max_lag months."""
    if external.empty or len(commodity_obs) < min_overlap + 2:
        return pd.DataFrame()
    s = commodity_obs.set_index("month")["price"].resample("MS").last()
    ry = np.log(s).diff()
    out = {}
    for col in external.columns:
        rx = np.log(external[col]).diff()
        row = {}
        for k in range(max_lag + 1):
            a, b = ry.align(rx.shift(k), join="inner")
            ok = a.notna() & b.notna()
            row[f"lag {k}m"] = float(a[ok].corr(b[ok])) \
                if ok.sum() >= min_overlap else np.nan
        out[col] = row
    return pd.DataFrame(out).T
