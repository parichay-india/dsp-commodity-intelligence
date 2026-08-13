"""
Ensemble strategies for the DSP Commodity Intelligence engine.

All weight-learning happens on an inner walk-forward inside the training
window only — the outer 20% test never touches weight selection, so ensemble
scores in the leaderboard are as honest as any single model's.

The annealed ensemble uses scipy's dual_annealing (generalized simulated
annealing, the classical member of the quantum-inspired metaheuristic
family) to search the weight simplex directly against validation MAPE.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import dual_annealing

EPS = 1e-9


def _mape(actual: np.ndarray, pred: np.ndarray) -> float:
    ok = np.isfinite(pred) & np.isfinite(actual) & (actual > 0)
    if ok.sum() == 0:
        return np.inf
    return float(np.mean(np.abs(actual[ok] - pred[ok]) / actual[ok]))


def _combine(P: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Row-wise weighted mean that tolerates missing model predictions."""
    out = np.full(P.shape[0], np.nan)
    for i in range(P.shape[0]):
        row = P[i]
        ok = np.isfinite(row) & (w > 0)
        if ok.any():
            out[i] = float(np.sum(row[ok] * w[ok]) / np.sum(w[ok]))
    return out


def learn_ensembles(P: np.ndarray, actual: np.ndarray, names: list[str],
                    seed: int = 42) -> dict[str, np.ndarray]:
    """P: (inner steps x models) price predictions. Returns name -> weights."""
    n_models = P.shape[1]
    mapes = np.array([_mape(actual, P[:, j]) for j in range(n_models)])
    order = np.argsort(mapes)
    usable = [j for j in order if np.isfinite(mapes[j])]
    pool = usable[: min(8, len(usable))]

    out: dict[str, np.ndarray] = {}
    if not pool:
        return out

    # ---- mean of the five best inner models
    w = np.zeros(n_models)
    for j in usable[:5]:
        w[j] = 1.0
    out["Ensemble: top-5 mean"] = w / max(w.sum(), EPS)

    # ---- inverse-error weights over the pool
    w = np.zeros(n_models)
    for j in pool:
        w[j] = 1.0 / (mapes[j] + 1e-4)
    out["Ensemble: inverse-error"] = w / w.sum()

    # ---- simulated-annealing-optimized weights (softmax parametrisation)
    if len(pool) >= 2 and np.isfinite(actual).sum() >= 3:
        sub = P[:, pool]

        def loss(theta):
            e = np.exp(theta - theta.max())
            ww = e / e.sum()
            return _mape(actual, _combine(sub, ww))

        try:
            res = dual_annealing(loss, bounds=[(-4, 4)] * len(pool),
                                 maxiter=60, seed=seed, no_local_search=False)
            e = np.exp(res.x - res.x.max())
            ww = e / e.sum()
            w = np.zeros(n_models)
            w[pool] = ww
            out["Ensemble: annealed weights"] = w
        except Exception:
            pass

    # ---- greedy forward selection with replacement (Caruana-style)
    sel: list[int] = []
    best_score = np.inf
    for _ in range(12):
        cand_best, cand_j = best_score, None
        for j in pool:
            trial = sel + [j]
            w = np.bincount(trial, minlength=n_models).astype(float)
            s = _mape(actual, _combine(P, w))
            if s < cand_best - 1e-9:
                cand_best, cand_j = s, j
        if cand_j is None:
            break
        sel.append(cand_j)
        best_score = cand_best
    if sel:
        w = np.bincount(sel, minlength=n_models).astype(float)
        out["Ensemble: greedy selection"] = w / w.sum()

    return out


def apply_ensemble(P_row: np.ndarray, w: np.ndarray) -> float:
    ok = np.isfinite(P_row) & (w > 0)
    if not ok.any():
        return np.nan
    return float(np.sum(P_row[ok] * w[ok]) / np.sum(w[ok]))
