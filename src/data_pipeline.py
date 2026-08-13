"""
Data pipeline for the DSP Commodity Intelligence engine.

Reads the raw SAP-style purchase order dump (MAIN SHEET), resolves a trustworthy
unit price for every PO line, quarantines partial-delivery distortions, and
builds per-commodity monthly price series plus ordering/consumption statistics.

Nothing in here invents data. Every resolved price carries a provenance flag,
and every dropped row lands in the quarantine audit file.

Provenance flags on resolved prices:
    OK              value / qty received, consistent with the commodity's band
    RESOLVED_PRQTY  value / PR qty  (delivery still in progress; PO qty ~ PR qty)
    RESOLVED_EST    PR estimate rate used (PO-derived rates implausible)
    DROPPED         no defensible rate could be established (kept only in audit)
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ----------------------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[1]
RAW_DEFAULT = ROOT / "data" / "raw" / "DATA_COMMODITY__PRICING.XLSX"
PROC = ROOT / "data" / "processed"

# ------------------------------------------------------------------- tuning constants
RATIO_LO, RATIO_HI = 0.40, 2.50   # PO/PR unit ratio treated as "estimate consistent"
BAND_K = 3.5                      # robust band width in MAD units (log space)
MIN_POINTS_FOR_MODEL = 20         # valid PO lines needed for full ML treatment
MIN_MONTHS_FOR_MODEL = 12         # distinct observed months needed


def _save_table(df: pd.DataFrame, name: str) -> Path:
    """Parquet when pyarrow exists, transparent csv.gz otherwise."""
    PROC.mkdir(parents=True, exist_ok=True)
    try:
        import pyarrow  # noqa: F401
        p = PROC / f"{name}.parquet"
        df.to_parquet(p, index=False)
    except Exception:
        p = PROC / f"{name}.csv.gz"
        df.to_csv(p, index=False, compression="gzip")
    return p


def load_table(name: str) -> pd.DataFrame:
    for ext, reader in ((".parquet", pd.read_parquet), (".csv.gz", pd.read_csv)):
        p = PROC / f"{name}{ext}"
        if p.exists():
            df = reader(p)
            for c in df.columns:
                if c in ("month", "PO Date", "PO Rel Date",
                         "first_po", "last_po", "last_obs_month"):
                    df[c] = pd.to_datetime(df[c])
            return df
    raise FileNotFoundError(f"processed table '{name}' not found in {PROC}")


def _norm_desc(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().upper()


def load_raw(path: str | Path = RAW_DEFAULT) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="MAIN SHEET")
    df.columns = [c.strip() for c in df.columns]
    df["Material Code"] = df["Material Code"].astype(str).str.strip()
    df["commodity"] = df["Material Description"].map(_norm_desc)
    for c in ("PO Date", "PO Rel Date"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in ("Quantity Received", "Total PO Value", "PR Est Value", "PR Qty."):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["Ordering Mode"] = df["Ordering Mode"].astype(str).str.strip()
    return df


# --------------------------------------------------------------- unit price resolution
def _robust_band(logvals: np.ndarray, k: float = BAND_K) -> tuple[float, float]:
    med = np.median(logvals)
    mad = np.median(np.abs(logvals - med)) * 1.4826
    mad = max(mad, 0.08)  # never collapse the band to a point
    return med - k * mad, med + k * mad


def resolve_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Attach resolved_price + provenance to every PO line of every commodity."""
    d = df.copy()
    qr, val = d["Quantity Received"], d["Total PO Value"]
    prq, prv = d["PR Qty."], d["PR Est Value"]

    d["po_unit"] = np.where((qr > 0) & (val > 0), val / qr, np.nan)
    d["pr_unit"] = np.where((prq > 0) & (prv > 0), prv / prq, np.nan)
    d["alt_unit"] = np.where((prq > 0) & (val > 0), val / prq, np.nan)
    d["ratio"] = d["po_unit"] / d["pr_unit"]

    d["resolved_price"] = np.nan
    d["provenance"] = "DROPPED"

    for _, idx in d.groupby("commodity").groups.items():
        g = d.loc[idx]
        # Pass 1: anchor band on estimate-consistent PO rates; fall back to PR rates
        anchor = g.loc[g["ratio"].between(RATIO_LO, RATIO_HI), "po_unit"].dropna()
        if len(anchor) < 5:
            anchor = pd.concat([anchor, g["pr_unit"].dropna()])
        if len(anchor) < 3:
            anchor = g["po_unit"].dropna()
        if len(anchor) == 0:
            continue
        lo, hi = _robust_band(np.log(anchor.clip(lower=1e-9)))

        def in_band(x):
            return np.isfinite(x) & (np.log(np.clip(x, 1e-9, None)) >= lo) & (
                np.log(np.clip(x, 1e-9, None)) <= hi)

        po_ok = in_band(g["po_unit"]) & (
            g["ratio"].between(RATIO_LO, RATIO_HI) | ~np.isfinite(g["ratio"]))
        alt_ok = in_band(g["alt_unit"]) & ~po_ok
        est_ok = in_band(g["pr_unit"]) & ~po_ok & ~alt_ok
        band_ok = in_band(g["po_unit"]) & ~po_ok & ~alt_ok & ~est_ok

        for mask, src, tag in ((po_ok, "po_unit", "OK"),
                               (alt_ok, "alt_unit", "RESOLVED_PRQTY"),
                               (est_ok, "pr_unit", "RESOLVED_EST"),
                               (band_ok, "po_unit", "OK")):
            if mask.any():
                sel = g.index[mask]
                d.loc[sel, "resolved_price"] = g.loc[mask, src].astype(float)
                d.loc[sel, "provenance"] = tag

    d["resolved_price"] = pd.to_numeric(d["resolved_price"], errors="coerce")
    return d


# ----------------------------------------------------------------- monthly series
def build_monthly(d: pd.DataFrame) -> pd.DataFrame:
    """Quantity-weighted monthly price per commodity on a continuous month grid.

    'observed' marks months holding at least one real resolved PO price. Gap
    months carry a log-linear interpolation purely so models have a regular
    grid to walk on; accuracy is only ever scored against observed months.
    """
    ok = d[d["provenance"] != "DROPPED"].dropna(subset=["resolved_price", "PO Date"])
    ok = ok[ok["resolved_price"] > 0].copy()
    ok["month"] = ok["PO Date"].dt.to_period("M").dt.to_timestamp()
    w = ok["Quantity Received"].clip(lower=0).fillna(0)
    ok["_w"] = np.where(w > 0, w, 1.0)
    ok["_pw"] = ok["resolved_price"] * ok["_w"]

    agg = ok.groupby(["commodity", "month"]).agg(
        pw=("_pw", "sum"), wsum=("_w", "sum"),
        qty=("Quantity Received", "sum"), n_po=("resolved_price", "size"),
        spend=("Total PO Value", "sum"),
    ).reset_index()
    agg["price"] = agg["pw"] / agg["wsum"]

    frames = []
    for com, g in agg.groupby("commodity"):
        g = g.sort_values("month").set_index("month")
        grid = pd.date_range(g.index.min(), g.index.max(), freq="MS")
        s = g.reindex(grid)
        s["commodity"] = com
        s["observed"] = s["price"].notna()
        s["log_price"] = np.log(s["price"])
        s["log_price"] = s["log_price"].interpolate(method="linear", limit_direction="both")
        s["price_filled"] = np.exp(s["log_price"])
        s["qty"] = s["qty"].fillna(0.0)
        s["n_po"] = s["n_po"].fillna(0).astype(int)
        s["spend"] = s["spend"].fillna(0.0)
        frames.append(s.reset_index().rename(columns={"index": "month"}))
    out = pd.concat(frames, ignore_index=True)
    return out[["commodity", "month", "price", "price_filled", "log_price",
                "observed", "qty", "n_po", "spend"]]


# --------------------------------------------------------------- commodity catalog
def build_catalog(d: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    ok = d[d["provenance"] != "DROPPED"].dropna(subset=["resolved_price", "PO Date"])
    rows = []
    for com, g in ok.groupby("commodity"):
        g = g.sort_values("PO Date")
        mm = monthly[monthly["commodity"] == com]
        obs = mm[mm["observed"]]
        dates = g["PO Date"].dt.normalize().drop_duplicates().sort_values()
        gaps = dates.diff().dt.days.dropna()
        ratio = g["ratio"].replace([np.inf, -np.inf], np.nan).dropna()
        ratio = ratio[ratio.between(0.2, 5)]
        rows.append({
            "commodity": com,
            "material_codes": ";".join(sorted(g["Material Code"].unique())[:6]),
            "n_po_valid": len(g),
            "n_po_raw": int((d["commodity"] == com).sum()),
            "n_months_observed": int(len(obs)),
            "first_po": g["PO Date"].min(), "last_po": g["PO Date"].max(),
            "total_spend": float(g["Total PO Value"].sum()),
            "last_price": float(obs["price"].iloc[-1]) if len(obs) else np.nan,
            "last_obs_month": obs["month"].max() if len(obs) else pd.NaT,
            "median_price": float(obs["price"].median()) if len(obs) else np.nan,
            "price_cv": float(obs["price"].std() / obs["price"].mean()) if len(obs) > 2 else np.nan,
            "median_order_gap_days": float(gaps.median()) if len(gaps) else np.nan,
            "p90_order_gap_days": float(gaps.quantile(0.9)) if len(gaps) else np.nan,
            "avg_monthly_qty": float(mm["qty"].mean()) if len(mm) else np.nan,
            "std_monthly_qty": float(mm["qty"].std()) if len(mm) else np.nan,
            "neg_ratio_median": float(ratio.median()) if len(ratio) else np.nan,
            "neg_below_est_share": float((ratio < 1).mean()) if len(ratio) else np.nan,
            "dominant_mode": g["Ordering Mode"].mode().iat[0] if len(g) else "",
            "modelable": (len(g) >= MIN_POINTS_FOR_MODEL and len(obs) >= MIN_MONTHS_FOR_MODEL),
        })
    cat = pd.DataFrame(rows).sort_values("total_spend", ascending=False).reset_index(drop=True)
    return cat


def run_pipeline(raw_path: str | Path = RAW_DEFAULT, verbose: bool = True) -> dict:
    raw = load_raw(raw_path)
    d = resolve_prices(raw)
    monthly = build_monthly(d)
    catalog = build_catalog(d, monthly)

    quarantine = d[d["provenance"].isin(["DROPPED", "RESOLVED_PRQTY", "RESOLVED_EST"])][
        ["commodity", "Material Code", "PO No", "PO Date", "Quantity Received",
         "Total PO Value", "PR Qty.", "PR Est Value", "po_unit", "pr_unit",
         "alt_unit", "ratio", "resolved_price", "provenance"]]

    paths = {
        "po_clean": _save_table(
            d[d["provenance"] != "DROPPED"], "po_clean"),
        "monthly_prices": _save_table(monthly, "monthly_prices"),
        "catalog": _save_table(catalog, "catalog"),
        "quarantine": _save_table(quarantine, "quarantine_audit"),
    }
    summary = {
        "rows_raw": int(len(raw)),
        "rows_priced": int((d["provenance"] != "DROPPED").sum()),
        "rows_dropped": int((d["provenance"] == "DROPPED").sum()),
        "resolved_prqty": int((d["provenance"] == "RESOLVED_PRQTY").sum()),
        "resolved_est": int((d["provenance"] == "RESOLVED_EST").sum()),
        "commodities_total": int(catalog.shape[0]),
        "commodities_modelable": int(catalog["modelable"].sum()),
        "span": [str(raw["PO Date"].min().date()), str(raw["PO Date"].max().date())],
    }
    (PROC / "pipeline_summary.json").write_text(json.dumps(summary, indent=2))
    if verbose:
        print(json.dumps(summary, indent=2))
    return {"summary": summary, "paths": {k: str(v) for k, v in paths.items()}}


if __name__ == "__main__":
    run_pipeline()
