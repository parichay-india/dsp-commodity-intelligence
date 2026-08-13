"""
End-to-end training orchestrator.

    python -m src.train_all            # resume-safe full run
    python -m src.train_all --refresh  # rebuild pipeline artifacts first

Stages
------
1. data pipeline artifacts (if absent or --refresh)
2. inner+outer walk-forward bake-off, every modelable commodity,
   checkpointed per commodity so an interrupted run resumes cleanly
3. champion refit on the full observed history -> 12-month forecast
   with empirical uncertainty bands from that champion's own backtest
   error distribution
4. decision signals (fuzzy verdicts, negotiation quartiles, inventory
   snapshot inputs) -> decision_signals.json

Re-running this script on a refreshed XLSX is the whole "self-learning"
loop: champions are re-selected from scratch against the newest data.
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import evaluate_commodity, filled_from_observed, month_index
from .data_pipeline import PROC, load_table, run_pipeline
from .decision_engine import compute_signal
from .ensemble import apply_ensemble
from .models import fit_and_forecast, model_zoo

warnings.filterwarnings("ignore")

LB_PATH = PROC / "leaderboard.csv"
CH_PATH = PROC / "champions.jsonl"
TP_PATH = PROC / "test_predictions.csv"
FC_PATH = PROC / "forecasts.csv"
SIG_PATH = PROC / "decision_signals.json"


def _done_commodities() -> set[str]:
    if not CH_PATH.exists():
        return set()
    return {json.loads(l)["commodity"] for l in CH_PATH.read_text().splitlines() if l.strip()}


def stage_bakeoff(monthly: pd.DataFrame, commodities: list[str],
                  budget_s: float | None = None,
                  progress_cb=None) -> bool:
    """Returns True when every commodity is done."""
    t_start = time.time()
    done = _done_commodities()
    todo = [c for c in commodities if c not in done]
    print(f"bake-off: {len(done)} done, {len(todo)} to go", flush=True)
    for i, com in enumerate(todo, 1):
        if budget_s and time.time() - t_start > budget_s:
            print(f"budget reached — pausing cleanly with "
                  f"{len(todo)-i+1} commodities remaining", flush=True)
            return False
        if progress_cb:
            progress_cb(i - 1, len(todo), com)
        t0 = time.time()
        res = evaluate_commodity(monthly, com)
        if res is None:
            with CH_PATH.open("a") as f:
                f.write(json.dumps({"commodity": com, "model": None}) + "\n")
            continue
        lb, preds, champ = res
        lb.to_csv(LB_PATH, mode="a", header=not LB_PATH.exists(), index=False)
        preds.to_csv(TP_PATH, mode="a", header=not TP_PATH.exists(), index=False)
        with CH_PATH.open("a") as f:
            f.write(json.dumps(champ, default=str) + "\n")
        print(f"[{i:3d}/{len(todo)}] {time.time()-t0:5.1f}s "
              f"{com[:44]:44s} -> {champ['model']} (MAPE {champ['mape']:.3f})",
              flush=True)
    return True


def _champion_forecast(monthly: pd.DataFrame, champ: dict, h_max: int = 12):
    """Refit the champion on the full observed history, forecast h=1..12."""
    g = monthly[(monthly["commodity"] == champ["commodity"]) & monthly["observed"]]
    g = g.sort_values("month")
    mi = month_index(g["month"])
    logp = np.log(g["price"].to_numpy(float))
    grid, y = filled_from_observed(mi, logp)
    start_month = int(grid[0] % 12)
    zoo = model_zoo()
    names = champ["model_names"]

    if champ["model"].startswith("Ensemble"):
        w = np.array(champ["ens_weights"][champ["model"]], dtype=float)
        base = {}
        for j, n in enumerate(names):
            if w[j] > 0:
                f = fit_and_forecast(zoo[n], y, h_max, start_month=start_month)
                base[j] = np.exp(f) if f is not None else None
        p50 = np.array([
            apply_ensemble(
                np.array([base[j][k] if base.get(j) is not None else np.nan
                          for j in range(len(names))]), w)
            for k in range(h_max)])
    else:
        f = fit_and_forecast(zoo[champ["model"]], y, h_max, start_month=start_month)
        if f is None:  # graceful fallback: hold last price
            f = np.full(h_max, y[-1])
        p50 = np.exp(f)

    q80 = champ.get("rel_err_q80")
    if q80 is None or not np.isfinite(q80) or q80 <= 0:
        q80 = 0.08
    mean_h = champ.get("mean_h") or 1.0
    hh = np.arange(1, h_max + 1)
    scale = np.clip(np.sqrt(hh / max(mean_h, 1.0)), 0.8, 2.5)
    band = np.clip(q80 * scale, 0.01, 0.60)
    last_month = pd.Timestamp(g["month"].iloc[-1])
    months = pd.date_range(last_month, periods=h_max + 1, freq="MS")[1:]
    return pd.DataFrame(dict(
        commodity=champ["commodity"], month=months, horizon=hh,
        p50=p50, p10=p50 * (1 - band), p90=p50 * (1 + band),
        model=champ["model"]))


def stage_forecasts(monthly: pd.DataFrame, only_missing: bool = False,
                    progress_cb=None) -> pd.DataFrame:
    champs = [json.loads(l) for l in CH_PATH.read_text().splitlines() if l.strip()]
    champs = [c for c in champs if c.get("model")]
    existing = None
    if only_missing and FC_PATH.exists():
        existing = pd.read_csv(FC_PATH, parse_dates=["month"])
        covered = set(existing["commodity"].unique())
        todo = [c for c in champs if c["commodity"] not in covered]
    else:
        todo = champs
    frames = []
    for i, ch in enumerate(todo):
        if progress_cb:
            progress_cb(i, len(todo), ch["commodity"])
        try:
            frames.append(_champion_forecast(monthly, ch))
        except Exception as e:
            print("forecast failed:", ch["commodity"], e, flush=True)
    new_fc = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["commodity", "month", "horizon", "p50", "p10", "p90", "model"])
    fc = pd.concat([existing, new_fc], ignore_index=True) \
        if existing is not None else new_fc
    fc.to_csv(FC_PATH, index=False)
    print(f"forecasts written for {fc['commodity'].nunique()} commodities "
          f"({len(todo)} refreshed)", flush=True)
    return fc


def incremental_update(progress_cb=None) -> dict:
    """After the pipeline has been rebuilt and stale artifacts invalidated:
    re-referee only the commodities without a champion, refresh only the
    forecasts that are missing, and rebuild all decision signals (they
    depend on the new as-of date). Returns a small summary."""
    t0 = time.time()
    monthly = load_table("monthly_prices")
    cat = load_table("catalog")
    commodities = cat[cat["modelable"]]["commodity"].tolist()
    n_before = len(_done_commodities())
    stage_bakeoff(monthly, commodities, progress_cb=progress_cb)
    n_retrained = len(_done_commodities()) - n_before
    fc = stage_forecasts(monthly, only_missing=True)
    stage_signals(monthly, fc)
    from .impact import snapshot_signals
    snapshot_signals()
    return dict(models_retrained=int(n_retrained),
                commodities_total=int(len(commodities)),
                seconds=round(time.time() - t0, 1))


def stage_signals(monthly: pd.DataFrame, fc: pd.DataFrame) -> None:
    cat = load_table("catalog")
    po = load_table("po_clean")
    asof = pd.Timestamp(po["PO Date"].max())
    ratios = po[po["ratio"].between(0.2, 5)].groupby("commodity")["ratio"] \
               .quantile([0.25, 0.75]).unstack()

    signals = {}
    for _, row in cat[cat["modelable"]].iterrows():
        com = row["commodity"]
        obs = monthly[(monthly["commodity"] == com) & monthly["observed"]] \
            .sort_values("month")
        if obs.empty:
            continue
        f = fc[fc["commodity"] == com].set_index("horizon")
        fdict = {}
        for h in (3, 6, 12):
            if h in f.index:
                fdict[f"p50_{h}"] = float(f.loc[h, "p50"])
                fdict[f"p10_{h}"] = float(f.loc[h, "p10"])
                fdict[f"p90_{h}"] = float(f.loc[h, "p90"])
        try:
            sig = compute_signal(obs, fdict, row, asof)
        except Exception as e:
            print("signal failed:", com, e, flush=True)
            continue
        sig["forecast"] = fdict
        sig["ratio_q25"] = float(ratios.loc[com, 0.25]) if com in ratios.index else None
        sig["ratio_q75"] = float(ratios.loc[com, 0.75]) if com in ratios.index else None
        signals[com] = sig
    SIG_PATH.write_text(json.dumps(
        {"asof": str(asof.date()), "signals": signals}, indent=1, default=str))
    print(f"decision signals written for {len(signals)} commodities", flush=True)


def main():
    refresh = "--refresh" in sys.argv
    need = not (PROC / "pipeline_summary.json").exists()
    if refresh or need:
        run_pipeline()
        for p in (LB_PATH, CH_PATH, TP_PATH, FC_PATH, SIG_PATH):
            p.unlink(missing_ok=True)
    budget = None
    if "--budget" in sys.argv:
        budget = float(sys.argv[sys.argv.index("--budget") + 1])
    monthly = load_table("monthly_prices")
    cat = load_table("catalog")
    commodities = cat[cat["modelable"]]["commodity"].tolist()
    complete = stage_bakeoff(monthly, commodities, budget_s=budget)
    if not complete:
        print("PAUSED — rerun to resume", flush=True)
        return
    fc = stage_forecasts(monthly)
    stage_signals(monthly, fc)
    from .impact import snapshot_signals
    n = snapshot_signals()
    print(f"signal ledger: {n} entries snapshotted", flush=True)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
