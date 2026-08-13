"""
Data access layer for the dashboard — pure functions, no streamlit imports,
so every piece of logic here is unit-testable outside the UI.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data_pipeline import PROC, load_table

SIG_PATH = PROC / "decision_signals.json"


def artifacts_ready() -> bool:
    need = ["monthly_prices", "catalog", "po_clean"]
    have_tables = all(
        (PROC / f"{n}.parquet").exists() or (PROC / f"{n}.csv.gz").exists()
        for n in need)
    return have_tables and (PROC / "forecasts.csv").exists() and SIG_PATH.exists()


def load_bundle() -> dict:
    """Everything the app needs, loaded once and cached by the caller."""
    monthly = load_table("monthly_prices")
    catalog = load_table("catalog")
    po = load_table("po_clean")
    quarantine = load_table("quarantine_audit")
    fc = pd.read_csv(PROC / "forecasts.csv", parse_dates=["month"])
    lb = pd.read_csv(PROC / "leaderboard.csv")
    tp = pd.read_csv(PROC / "test_predictions.csv", parse_dates=["month"])
    champions = pd.read_json(PROC / "champions.jsonl", lines=True)
    sig_raw = json.loads(SIG_PATH.read_text())
    summary = json.loads((PROC / "pipeline_summary.json").read_text())
    for col in ("first_po", "last_po", "last_obs_month"):
        catalog[col] = pd.to_datetime(catalog[col])
    return dict(monthly=monthly, catalog=catalog, po=po, quarantine=quarantine,
                forecasts=fc, leaderboard=lb, test_preds=tp,
                champions=champions,
                signals=sig_raw["signals"], asof=pd.Timestamp(sig_raw["asof"]),
                summary=summary)


def action_board(bundle: dict) -> pd.DataFrame:
    cat = bundle["catalog"]
    sig = bundle["signals"]
    monthly = bundle["monthly"]
    rows = []
    for _, r in cat[cat["modelable"]].iterrows():
        s = sig.get(r["commodity"])
        if not s:
            continue
        obs = monthly[(monthly["commodity"] == r["commodity"]) & monthly["observed"]]
        spark = obs.sort_values("month")["price"].tail(24).tolist()
        rows.append(dict(
            commodity=r["commodity"],
            signal=s["label"], score=s["score"],
            move_3m=s["exp_move_3m"], move_6m=s["exp_move_6m"],
            move_12m=s["exp_move_12m"],
            last_price=s["last_price"],
            months_since=s["months_since_last"],
            cycle_m=s["cycle_months"],
            spend_cr=r["total_spend"] / 1e7,
            trend=spark,
            last_po=r["last_po"],
        ))
    df = pd.DataFrame(rows)
    order = {"BUY NOW": 0, "BUY / STAGGER": 1, "MONITOR": 2, "WAIT": 3, "HOLD OFF": 4}
    df["_o"] = df["signal"].map(order)
    return df.sort_values(["_o", "spend_cr"], ascending=[True, False]) \
             .drop(columns="_o").reset_index(drop=True)


def kpis(bundle: dict) -> dict:
    po = bundle["po"]
    cat = bundle["catalog"]
    asof = bundle["asof"]
    last12 = po[po["PO Date"] > asof - pd.DateOffset(months=12)]
    champs = pd.read_json(PROC / "champions.jsonl", lines=True)
    champs = champs[champs["model"].notna()]
    board = action_board(bundle)
    return dict(
        spend_12m_cr=float(last12["Total PO Value"].sum() / 1e7),
        n_po_12m=int(len(last12)),
        n_total=int(len(cat)), n_model=int(cat["modelable"].sum()),
        n_buy=int((board["signal"].isin(["BUY NOW", "BUY / STAGGER"])).sum()),
        n_overdue=int((board["months_since"] > board["cycle_m"] * 1.1).sum()),
        med_mape=float(champs["mape"].median()),
        asof=asof,
    )


def commodity_pack(bundle: dict, com: str) -> dict:
    monthly = bundle["monthly"]
    obs = monthly[(monthly["commodity"] == com) & monthly["observed"]] \
        .sort_values("month")
    filled = monthly[monthly["commodity"] == com].sort_values("month")
    fc = bundle["forecasts"]
    fc = fc[fc["commodity"] == com].sort_values("month")
    lb = bundle["leaderboard"]
    lb = lb[lb["commodity"] == com].sort_values("mape")
    tp = bundle["test_preds"]
    tp = tp[tp["commodity"] == com]
    po = bundle["po"]
    po = po[po["commodity"] == com].sort_values("PO Date")
    cat = bundle["catalog"]
    row = cat[cat["commodity"] == com].iloc[0] if (cat["commodity"] == com).any() else None
    sig = bundle["signals"].get(com)
    chd = bundle["champions"]
    champ = chd[chd["commodity"] == com].iloc[0].to_dict() \
        if (chd["commodity"] == com).any() else None
    return dict(obs=obs, filled=filled, forecast=fc, leaderboard=lb,
                test_preds=tp, po=po, cat=row, signal=sig, champion=champ)


def seasonality_matrix(obs: pd.DataFrame) -> pd.DataFrame:
    d = obs.copy()
    d["year"] = d["month"].dt.year
    d["mon"] = d["month"].dt.month
    piv = d.pivot_table(index="mon", columns="year", values="price", aggfunc="mean")
    piv.index = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][: len(piv)] \
        if len(piv) == 12 else piv.index
    return piv


def monthly_returns(obs: pd.DataFrame) -> pd.Series:
    s = obs.set_index("month")["price"].astype(float)
    s = s.resample("MS").last().dropna()
    return np.log(s).diff().dropna()


# ============================================================ forecast registry
METHOD_NOTES = {
    "Naive (last price)": "Repeats the last observed price — the hardest "
        "baseline to beat on sticky, contract-anchored rates.",
    "Seasonal naive (12m)": "Repeats the price from the same month last "
        "year — captures annual rhythms (monsoon, budget cycles).",
    "Drift": "Extends the straight line from first to last observation.",
    "Moving average (auto-k)": "Average of the last k months (k self-tuned "
        "from 3/6/12) held flat — smooths noise, tracks level.",
    "Simple exp. smoothing": "Weighted average where recent months count "
        "exponentially more; the weight tunes itself.",
    "Holt trend (damped-auto)": "Smooths level and trend together, damping "
        "the trend so recent run-ups don't extrapolate forever.",
    "Holt-Winters seasonal": "Level + trend + a smoothed offset for each "
        "calendar month.",
    "Theta method": "Averages a calm long-term trend line with an "
        "amplified short-term view — the M3-competition winner.",
    "Linear trend": "Best straight line through log prices — constant "
        "percentage drift, ideal for steadily inflating materials.",
    "Autoregressive (ridge)": "Next month as a restrained weighted mix of "
        "the last p months; regression finds the weights.",
    "Bayesian ridge (lags)": "Lag regression where the data itself infers "
        "how much restraint to apply — naturally cautious on short "
        "histories.",
    "Random forest": "Hundreds of decision trees on lag/seasonality "
        "features, averaged.",
    "Extra trees": "A forest with extra randomness in its splits — more "
        "diverse opinions, steadier average.",
    "Gradient boosting": "Small trees built in sequence, each correcting "
        "the errors of the team so far.",
    "Hist gradient boosting": "Fast, regularised boosting (the LightGBM "
        "idea) — the strongest pure-ML performer here.",
    "Support vector (RBF)": "Fits the flattest smooth curve within a "
        "tolerance tube around the data.",
    "K-nearest neighbours": "Finds the five most similar past moments and "
        "averages what happened next.",
    "Neural net (MLP)": "A small trained network of weighted connections "
        "with early stopping against overfitting.",
    "Gaussian process": "Averages every smooth curve consistent with the "
        "data, weighted by plausibility — strong on small samples.",
    "Ensemble: top-5 mean": "Equal-weight blend of the five best "
        "validation models.",
    "Ensemble: inverse-error": "Blend weighted by 1 ÷ each model's "
        "validation error.",
    "Ensemble: annealed weights": "Blend weights tuned by simulated "
        "annealing against validation error.",
    "Ensemble: greedy selection": "Caruana's method — repeatedly add "
        "whichever model most improves the blend.",
}


def confidence_score(mape: float, mase: float, n_test: int) -> float:
    """0–100 confidence in a commodity's forecasts, from three honest
    ingredients: accuracy (MAPE vs a 30% floor), reliability vs naive
    (MASE, full credit at ≤0.7, none at ≥1.3), and evidence (test months,
    full credit at 10+). Weights 55/30/15. Purely descriptive — the
    formula is printed beside the table it scores."""
    acc = max(0.0, min(1.0, 1.0 - float(mape) / 0.30))
    rel = max(0.0, min(1.0, (1.3 - float(mase)) / 0.6))
    evid = max(0.0, min(1.0, float(n_test) / 10.0))
    return round(100 * (0.55 * acc + 0.30 * rel + 0.15 * evid), 0)


def registry_frame(bundle: dict) -> pd.DataFrame:
    ch = bundle["champions"].copy()
    cat = bundle["catalog"][["commodity", "total_spend"]]
    df = ch.merge(cat, on="commodity", how="left")
    df["method"] = df["model"].map(METHOD_NOTES).fillna("—")
    df["confidence"] = [confidence_score(m, s, n) for m, s, n in
                        zip(df["mape"], df["mase"], df["n_test"])]
    df["grade"] = pd.cut(df["confidence"], [-1, 55, 75, 101],
                         labels=["Use with care", "Moderate", "High"])
    df["spend_cr"] = df["total_spend"] / 1e7
    cols = ["commodity", "spend_cr", "model", "method", "mape", "rmse",
            "mase", "n_test", "confidence", "grade"]
    return df[cols].sort_values("spend_cr", ascending=False)                    .reset_index(drop=True)
