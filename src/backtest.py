"""
Walk-forward evaluation engine — the referee of the model bake-off.

Protocol per commodity (chronological, leakage-safe):

  observed months  ──────────────────────────────► time
  |──────────── 80% train ────────────|─── 20% test ───|
                     |── inner val ──|
                     (ensemble weights learned here only)

At every scored step the monthly grid is rebuilt from *only the observed
prices known at that moment* (past-only interpolation), so no future point
can leak backwards through gap-filling. Each model then forecasts across
the true gap to the next observed month — if the next real PO landed four
months later, the model is scored on a genuine 4-step-ahead forecast.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .ensemble import apply_ensemble, learn_ensembles
from .models import fit_and_forecast, model_zoo

MIN_TEST = 4
INNER_MAX = 8


def month_index(months: pd.Series) -> np.ndarray:
    m = pd.to_datetime(months)
    return (m.dt.year * 12 + m.dt.month).to_numpy()


def filled_from_observed(mi: np.ndarray, logp: np.ndarray):
    """Past-only monthly grid: linear interpolation between observed months."""
    grid = np.arange(mi[0], mi[-1] + 1)
    return grid, np.interp(grid, mi, logp)


def _series(monthly: pd.DataFrame, commodity: str):
    g = monthly[(monthly["commodity"] == commodity) & monthly["observed"]]
    g = g.sort_values("month")
    return month_index(g["month"]), np.log(g["price"].to_numpy(float)), g["month"].to_numpy()


def walk_forward(mi, logp, eval_idx, zoo):
    """Forecast every observed month in eval_idx using only earlier observations.
    Returns preds[model][k] (price space) plus actual prices and horizons."""
    names = list(zoo)
    preds = {n: np.full(len(eval_idx), np.nan) for n in names}
    horizons = np.zeros(len(eval_idx), int)
    actual = np.exp(logp[eval_idx])
    for k, i in enumerate(eval_idx):
        grid, y = filled_from_observed(mi[:i], logp[:i])
        h = int(mi[i] - grid[-1])
        horizons[k] = h
        start_month = int(grid[0] % 12)
        for n in names:
            f = fit_and_forecast(zoo[n], y, h, start_month=start_month)
            if f is not None:
                preds[n][k] = float(np.exp(f[-1]))
    return preds, actual, horizons


def _metrics(actual, pred, horizons, naive_mae):
    ok = np.isfinite(pred)
    cov = ok.mean()
    if ok.sum() == 0:
        return dict(mape=np.inf, smape=np.inf, rmse=np.inf, mase=np.inf,
                    coverage=0.0, n_scored=0, mean_h=np.nan)
    a, p = actual[ok], pred[ok]
    return dict(
        mape=float(np.mean(np.abs(a - p) / a)),
        smape=float(np.mean(2 * np.abs(a - p) / (np.abs(a) + np.abs(p)))),
        rmse=float(np.sqrt(np.mean((a - p) ** 2))),
        mase=float(np.mean(np.abs(a - p)) / max(naive_mae, 1e-9)),
        coverage=float(cov), n_scored=int(ok.sum()),
        mean_h=float(np.mean(horizons[ok])),
    )


def evaluate_commodity(monthly: pd.DataFrame, commodity: str, seed: int = 42):
    """Full inner+outer walk-forward for one commodity.

    Returns (leaderboard_rows, prediction_rows, champion_info) or None when
    the observed history is too thin to referee fairly.
    """
    mi, logp, months = _series(monthly, commodity)
    n = len(mi)
    if n < 12:
        return None
    n_test = max(MIN_TEST, int(np.ceil(0.2 * n)))
    if n - n_test < 10:
        n_test = max(3, n - 10)
    test_idx = list(range(n - n_test, n))
    n_inner = min(INNER_MAX, max(3, (n - n_test) // 4))
    inner_idx = list(range(n - n_test - n_inner, n - n_test))

    zoo = model_zoo()
    names = list(zoo)

    # naive scale for MASE, computed on training observations only
    train_prices = np.exp(logp[: n - n_test])
    naive_mae = float(np.mean(np.abs(np.diff(train_prices)))) if len(train_prices) > 1 else 1.0

    # ---- inner pass: learn ensemble weights on train-only ground
    inner_preds, inner_actual, _ = walk_forward(mi, logp, inner_idx, zoo)
    P_inner = np.column_stack([inner_preds[n_] for n_ in names])
    weights = learn_ensembles(P_inner, inner_actual, names, seed=seed)

    # ---- outer pass: the 20% championship
    outer_preds, outer_actual, outer_h = walk_forward(mi, logp, test_idx, zoo)
    P_outer = np.column_stack([outer_preds[n_] for n_ in names])
    for ens_name, w in weights.items():
        outer_preds[ens_name] = np.array(
            [apply_ensemble(P_outer[k], w) for k in range(len(test_idx))])

    rows, pred_rows = [], []
    for name, pred in outer_preds.items():
        m = _metrics(outer_actual, pred, outer_h, naive_mae)
        m.update(commodity=commodity, model=name,
                 kind="ensemble" if name.startswith("Ensemble") else "single")
        rows.append(m)
        for k, i in enumerate(test_idx):
            pred_rows.append(dict(commodity=commodity, model=name,
                                  month=months[i], actual=outer_actual[k],
                                  pred=pred[k], horizon=int(outer_h[k])))

    lb = pd.DataFrame(rows)
    eligible = lb[(lb["coverage"] >= 0.7) & np.isfinite(lb["mape"])]
    if eligible.empty:
        eligible = lb[np.isfinite(lb["mape"])]
    champ = eligible.sort_values(["mape", "rmse"]).iloc[0]
    rel_err = np.abs(outer_actual - outer_preds[champ["model"]]) / outer_actual
    rel_err = rel_err[np.isfinite(rel_err)]

    champion = dict(
        commodity=commodity, model=str(champ["model"]),
        mape=float(champ["mape"]), rmse=float(champ["rmse"]),
        mase=float(champ["mase"]), n_test=int(len(test_idx)),
        mean_h=float(champ["mean_h"]),
        rel_err_q50=float(np.quantile(rel_err, 0.5)) if len(rel_err) else np.nan,
        rel_err_q80=float(np.quantile(rel_err, 0.8)) if len(rel_err) else np.nan,
        ens_weights={k: v.tolist() for k, v in weights.items()},
        model_names=names,
    )
    return lb, pd.DataFrame(pred_rows), champion
