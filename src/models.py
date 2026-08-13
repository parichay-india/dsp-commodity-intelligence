"""
Forecasting model zoo for the DSP Commodity Intelligence engine.

Every model works on the monthly log-price grid and exposes the same tiny
interface:   fit(y) -> self,   forecast(h) -> np.ndarray of h values.

Statistical methods are implemented from first principles (no statsmodels
dependency, so the exact same code runs identically on Streamlit Cloud, a
plant desktop, or an air-gapped machine). Machine-learning forecasters wrap
scikit-learn regressors around a shared lag/seasonality feature builder and
forecast recursively.

y is always the *filled* monthly log-price series; accuracy is only ever
scored against genuinely observed months (see backtest.py).
"""

from __future__ import annotations

import numpy as np

from sklearn.ensemble import (ExtraTreesRegressor, GradientBoostingRegressor,
                              HistGradientBoostingRegressor, RandomForestRegressor)
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.linear_model import BayesianRidge, LinearRegression, Ridge
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

SEASON = 12
RNG = 42


# ============================================================== helper machinery
def _val_split(y: np.ndarray, k: int = 12) -> tuple[np.ndarray, np.ndarray]:
    """Last-k holdout inside the training window, used only for self-tuning."""
    k = min(k, max(2, len(y) // 4))
    return y[:-k], y[-k:]


def _sse_one_step(fitter, y_tr: np.ndarray, y_val: np.ndarray) -> float:
    """One-step-ahead squared error of a fit/forecast pair over a validation tail."""
    err = 0.0
    hist = y_tr.copy()
    for actual in y_val:
        try:
            f = fitter(hist)
            err += float((f - actual) ** 2)
        except Exception:
            err += 1e6
        hist = np.append(hist, actual)
    return err


# ============================================================== statistical models
class NaiveLast:
    name = "Naive (last price)"
    def fit(self, y): self.last = y[-1]; return self
    def forecast(self, h): return np.full(h, self.last)


class SeasonalNaive:
    name = "Seasonal naive (12m)"
    def fit(self, y):
        self.y = y
        return self
    def forecast(self, h):
        n = len(self.y)
        if n < SEASON:
            return np.full(h, self.y[-1])
        return np.array([self.y[n - SEASON + (i % SEASON)] for i in range(h)])


class Drift:
    name = "Drift"
    def fit(self, y):
        self.last = y[-1]
        self.slope = (y[-1] - y[0]) / max(len(y) - 1, 1)
        return self
    def forecast(self, h):
        return self.last + self.slope * np.arange(1, h + 1)


class MovingAverage:
    name = "Moving average (auto-k)"
    def fit(self, y):
        best, self.k = np.inf, 3
        tr, va = _val_split(y)
        for k in (3, 6, 12):
            if len(tr) < k: continue
            sse = _sse_one_step(lambda h, k=k: float(np.mean(h[-k:])), tr, va)
            if sse < best: best, self.k = sse, k
        self.level = float(np.mean(y[-self.k:]))
        return self
    def forecast(self, h): return np.full(h, self.level)


def _ses_level(y: np.ndarray, alpha: float) -> float:
    l = y[0]
    for v in y[1:]:
        l = alpha * v + (1 - alpha) * l
    return l


class SES:
    name = "Simple exp. smoothing"
    def fit(self, y):
        tr, va = _val_split(y)
        best, self.alpha = np.inf, 0.3
        for a in (0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9):
            sse = _sse_one_step(lambda h, a=a: _ses_level(h, a), tr, va)
            if sse < best: best, self.alpha = sse, a
        self.level = _ses_level(y, self.alpha)
        return self
    def forecast(self, h): return np.full(h, self.level)


def _holt_state(y, a, b, phi):
    l, t = y[0], y[1] - y[0] if len(y) > 1 else 0.0
    for v in y[1:]:
        l_prev = l
        l = a * v + (1 - a) * (l_prev + phi * t)
        t = b * (l - l_prev) + (1 - b) * phi * t
    return l, t


class Holt:
    name = "Holt trend (damped-auto)"
    def fit(self, y):
        tr, va = _val_split(y)
        best, self.p = np.inf, (0.3, 0.1, 1.0)
        for a in (0.2, 0.4, 0.6, 0.8):
            for b in (0.05, 0.15, 0.3):
                for phi in (1.0, 0.9, 0.8):
                    def f(hist, a=a, b=b, phi=phi):
                        l, t = _holt_state(hist, a, b, phi)
                        return l + phi * t
                    sse = _sse_one_step(f, tr, va)
                    if sse < best: best, self.p = sse, (a, b, phi)
        a, b, phi = self.p
        self.l, self.t, self.phi = *_holt_state(y, a, b, phi), phi
        return self
    def forecast(self, h):
        damp = np.cumsum(self.phi ** np.arange(1, h + 1))
        return self.l + damp * self.t


class HoltWinters:
    """Additive Holt-Winters on the log scale, season = 12."""
    name = "Holt-Winters seasonal"
    def _run(self, y, a, b, g):
        m = SEASON
        l = float(np.mean(y[:m]))
        t = (np.mean(y[m:2 * m]) - np.mean(y[:m])) / m
        s = list(y[:m] - l)
        for i in range(m, len(y)):
            l_prev = l
            l = a * (y[i] - s[i - m]) + (1 - a) * (l + t)
            t = b * (l - l_prev) + (1 - b) * t
            s.append(g * (y[i] - l) + (1 - g) * s[i - m])
        return l, t, s
    def fit(self, y):
        if len(y) < 2 * SEASON + 6:
            raise ValueError("series too short for seasonal model")
        tr, va = _val_split(y, 6)
        best, self.p = np.inf, (0.3, 0.05, 0.1)
        for a in (0.2, 0.4, 0.6):
            for b in (0.02, 0.1):
                for g in (0.05, 0.2):
                    def f(hist, a=a, b=b, g=g):
                        l, t, s = self._run(hist, a, b, g)
                        return l + t + s[len(hist) - SEASON]
                    sse = _sse_one_step(f, tr, va)
                    if sse < best: best, self.p = sse, (a, b, g)
        self.l, self.t, self.s = self._run(y, *self.p)
        self.n = len(y)
        return self
    def forecast(self, h):
        out = []
        for i in range(1, h + 1):
            out.append(self.l + i * self.t + self.s[self.n - SEASON + ((i - 1) % SEASON)])
        return np.array(out)


class Theta:
    """Classic Theta(0,2): average of a linear-trend line and SES on the
    theta=2 line — the method that won the M3 competition."""
    name = "Theta method"
    def fit(self, y):
        n = len(y)
        t = np.arange(n, dtype=float)
        self.b, self.a = np.polyfit(t, y, 1)
        z = 2.0 * y - (self.a + self.b * t)
        tr, va = _val_split(z)
        best, self.alpha = np.inf, 0.3
        for al in (0.1, 0.2, 0.3, 0.5, 0.7):
            sse = _sse_one_step(lambda h, al=al: _ses_level(h, al), tr, va)
            if sse < best: best, self.alpha = sse, al
        self.z_level = _ses_level(z, self.alpha)
        self.n = n
        return self
    def forecast(self, h):
        hh = np.arange(1, h + 1)
        trend = self.a + self.b * (self.n - 1 + hh)
        return 0.5 * self.z_level + 0.5 * trend


class LinearTrend:
    name = "Linear trend"
    def fit(self, y):
        n = len(y); t = np.arange(n, dtype=float)
        self.b, self.a = np.polyfit(t, y, 1)
        self.n = n
        return self
    def forecast(self, h):
        return self.a + self.b * (self.n - 1 + np.arange(1, h + 1))


class RidgeAR:
    name = "Autoregressive (ridge)"
    def _mat(self, y, p):
        X = np.column_stack([y[p - k - 1: len(y) - k - 1] for k in range(p)])
        return X, y[p:]
    def fit(self, y):
        tr, va = _val_split(y)
        best, self.p, self.alpha = np.inf, 3, 1.0
        for p in (3, 6, 12):
            if len(tr) <= p + 4: continue
            for al in (0.1, 1.0, 10.0):
                def f(hist, p=p, al=al):
                    if len(hist) <= p + 2: raise ValueError
                    X, yy = self._mat(hist, p)
                    m = Ridge(alpha=al).fit(X, yy)
                    return float(m.predict(hist[-p:][::-1].reshape(1, -1))[0])
                sse = _sse_one_step(f, tr, va)
                if sse < best: best, self.p, self.alpha = sse, p, al
        X, yy = self._mat(y, self.p)
        self.model = Ridge(alpha=self.alpha).fit(X, yy)
        self.hist = y.copy()
        return self
    def forecast(self, h):
        hist = self.hist.copy()
        out = []
        for _ in range(h):
            x = hist[-self.p:][::-1].reshape(1, -1)
            v = float(self.model.predict(x)[0])
            out.append(v); hist = np.append(hist, v)
        return np.array(out)


# ============================================================== ML feature machinery
LAGS = (1, 2, 3, 4, 6, 9, 12)
ROLLS = (3, 6, 12)


def _feat_row(hist: np.ndarray, month_idx: int, t_idx: int, t_scale: float) -> np.ndarray:
    f = [hist[-k] for k in LAGS]
    f += [float(np.mean(hist[-w:])) for w in ROLLS]
    f += [float(np.std(hist[-w:])) for w in ROLLS]
    f.append(hist[-1] - hist[-2])
    f += [np.sin(2 * np.pi * month_idx / 12), np.cos(2 * np.pi * month_idx / 12)]
    f.append(t_idx / t_scale)
    return np.array(f, dtype=float)


def build_xy(y: np.ndarray, start_month: int) -> tuple[np.ndarray, np.ndarray]:
    warm = max(LAGS)
    X, Y = [], []
    t_scale = max(len(y), 24)
    for i in range(warm, len(y)):
        X.append(_feat_row(y[:i], (start_month + i) % 12, i, t_scale))
        Y.append(y[i])
    return np.array(X), np.array(Y)


class MLForecaster:
    """Recursive multi-step wrapper around any sklearn regressor."""
    def __init__(self, factory, name, scale=False, min_n=30):
        self.factory, self.name, self.scale, self.min_n = factory, name, scale, min_n

    def fit(self, y, start_month=0):
        if len(y) < self.min_n:
            raise ValueError("series too short for ML model")
        X, Y = build_xy(y, start_month)
        est = self.factory()
        self.model = make_pipeline(StandardScaler(), est) if self.scale else est
        self.model.fit(X, Y)
        self.hist = y.copy()
        self.start_month = start_month
        self.t_scale = max(len(y), 24)
        return self

    def forecast(self, h):
        hist = self.hist.copy()
        out = []
        for step in range(h):
            i = len(hist)
            x = _feat_row(hist, (self.start_month + i) % 12, i, self.t_scale).reshape(1, -1)
            v = float(self.model.predict(x)[0])
            out.append(v); hist = np.append(hist, v)
        return np.array(out)


class GPForecaster(MLForecaster):
    """Gaussian process on a capped recent window (kernel cost is cubic)."""
    CAP = 84
    def fit(self, y, start_month=0):
        y2 = y[-self.CAP:] if len(y) > self.CAP else y
        offset = len(y) - len(y2)
        return super().fit(y2, start_month=(start_month + offset) % 12)


# ============================================================== the zoo registry
def model_zoo() -> dict:
    """name -> callable returning a fresh unfitted model."""
    zoo = {
        "Naive (last price)": NaiveLast,
        "Seasonal naive (12m)": SeasonalNaive,
        "Drift": Drift,
        "Moving average (auto-k)": MovingAverage,
        "Simple exp. smoothing": SES,
        "Holt trend (damped-auto)": Holt,
        "Holt-Winters seasonal": HoltWinters,
        "Theta method": Theta,
        "Linear trend": LinearTrend,
        "Autoregressive (ridge)": RidgeAR,
    }
    ml = {
        "Random forest": (lambda: RandomForestRegressor(
            n_estimators=120, min_samples_leaf=2, random_state=RNG, n_jobs=1), False),
        "Extra trees": (lambda: ExtraTreesRegressor(
            n_estimators=120, min_samples_leaf=2, random_state=RNG, n_jobs=1), False),
        "Gradient boosting": (lambda: GradientBoostingRegressor(
            n_estimators=150, learning_rate=0.05, max_depth=3,
            subsample=0.9, random_state=RNG), False),
        "Hist gradient boosting": (lambda: HistGradientBoostingRegressor(
            max_iter=180, learning_rate=0.06, max_depth=3,
            l2_regularization=1.0, random_state=RNG), False),
        "Support vector (RBF)": (lambda: SVR(C=3.0, epsilon=0.01, gamma="scale"), True),
        "K-nearest neighbours": (lambda: KNeighborsRegressor(
            n_neighbors=5, weights="distance"), True),
        "Neural net (MLP)": (lambda: MLPRegressor(
            hidden_layer_sizes=(24,), alpha=1e-3, max_iter=400,
            early_stopping=True, n_iter_no_change=15, random_state=RNG), True),
        "Bayesian ridge (lags)": (lambda: BayesianRidge(), True),
    }
    for name, (fac, scale) in ml.items():
        zoo[name] = (lambda fac=fac, name=name, scale=scale:
                     MLForecaster(fac, name, scale=scale))
    zoo["Gaussian process"] = (lambda: GPForecaster(
        lambda: GaussianProcessRegressor(
            kernel=ConstantKernel(1.0) * RBF(length_scale=3.0)
                   + WhiteKernel(noise_level=0.05),
            normalize_y=True, random_state=RNG, alpha=1e-6),
        "Gaussian process", scale=True))
    return zoo


def fit_and_forecast(factory, y_log: np.ndarray, h: int, start_month: int = 0):
    """Uniform fit/forecast entry. Returns None when a model declines the series."""
    try:
        m = factory()
        if isinstance(m, (MLForecaster,)):
            m.fit(y_log, start_month=start_month)
        else:
            m.fit(y_log)
        f = np.asarray(m.forecast(h), dtype=float)
        if not np.all(np.isfinite(f)):
            return None
        return f
    except Exception:
        return None
