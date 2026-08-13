"""
Impact engine — puts a rupee figure on following (or ignoring) the engine.

Three honest lenses, clearly separated in the UI:

1. ON THE TABLE (prospective): today's live signals × each commodity's
   typical cycle volume × the forecast move = money currently at stake.
   A forecast, labelled as one.

2. VERIFIED LEDGER (retrospective, grows with every upload): every time
   signals are regenerated, they are snapshotted to an append-only ledger.
   When later uploads bring actual PO prices, each matured signal is scored:
   did the forecast direction come true, and what did following the call
   save or cost on that commodity's real purchase volume? Cumulative impact
   builds itself, upload by upload.

3. HELD-OUT PROOF (available on day one): the walk-forward test window —
   months the champions never saw — replayed as buy-early / buy-on-schedule
   decisions, scored against BOTH naive habits (always lock immediately,
   always wait for the scheduled month) and against perfect foresight.
   Quantities are the tonnages actually purchased in those months.

No lens ever mixes forecast with fact; each states which it is.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data_pipeline import PROC

LEDGER = PROC / "signal_history.jsonl"
DECISION_BAND = 0.015          # ±1.5%: forecast moves inside this are "flat"
BUY_FAMILY = ("BUY NOW", "BUY / STAGGER")
WAIT_FAMILY = ("WAIT", "HOLD OFF")


# ------------------------------------------------------------- 1. prospective
def value_on_table(signals: dict, catalog: pd.DataFrame) -> pd.DataFrame:
    cat = catalog.set_index("commodity")
    rows = []
    for com, s in signals.items():
        if s["label"] == "MONITOR" or com not in cat.index:
            continue
        qty = cat.loc[com, "avg_monthly_qty"] * max(s.get("cycle_months", 3), 1)
        move = s.get("exp_move_3m", 0.0)
        if not (np.isfinite(qty) and np.isfinite(move)):
            continue
        at_stake = abs(move) * s["last_price"] * qty
        rows.append(dict(
            commodity=com, signal=s["label"], score=s["score"],
            exp_move_3m=move, last_price=s["last_price"],
            stake_qty=float(qty), at_stake=float(at_stake),
            direction="rise" if move > 0 else "fall"))
    df = pd.DataFrame(rows)
    return df.sort_values("at_stake", ascending=False).reset_index(drop=True) \
        if len(df) else df


# ------------------------------------------------------------------ 2. ledger
def snapshot_signals(force: bool = False) -> int:
    """Append today's signals to the ledger, once per as-of date."""
    sig_path = PROC / "decision_signals.json"
    if not sig_path.exists():
        return 0
    payload = json.loads(sig_path.read_text())
    asof = payload["asof"]
    if LEDGER.exists() and not force:
        for line in LEDGER.read_text().splitlines():
            if line.strip() and json.loads(line).get("asof") == asof:
                return 0                     # this as-of already snapshotted
    from .data_pipeline import load_table
    cat = load_table("catalog").set_index("commodity")
    n = 0
    with LEDGER.open("a") as f:
        for com, s in payload["signals"].items():
            qty = np.nan
            if com in cat.index:
                qty = float(cat.loc[com, "avg_monthly_qty"]
                            * max(s.get("cycle_months", 3), 1))
            f.write(json.dumps(dict(
                asof=asof, commodity=com, label=s["label"],
                score=s["score"], exp_move_3m=s.get("exp_move_3m"),
                last_price=s.get("last_price"), stake_qty=qty,
                cycle_m=s.get("cycle_months")), default=str) + "\n")
            n += 1
    return n


def read_ledger() -> pd.DataFrame:
    if not LEDGER.exists():
        return pd.DataFrame()
    recs = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
    df = pd.DataFrame(recs)
    if len(df):
        df["asof"] = pd.to_datetime(df["asof"])
    return df


def evaluate_matured(monthly: pd.DataFrame,
                     window_m: tuple[int, int] = (2, 5)) -> pd.DataFrame:
    """Score ledger entries whose 3-month horizon has actual prices.

    For each snapshot: find the observed price nearest to asof+3m (accepting
    2–5 months out). Direction verdict tests the forecast sign. Rupee impact
    prices the follow-vs-ignore choice on the snapshot's stake quantity:
    a BUY call followed = bought at snapshot price instead of the matured
    price; a WAIT call followed = deferred to the matured price instead of
    locking at the snapshot price.
    """
    led = read_ledger()
    if led.empty:
        return led
    obs = monthly[monthly["observed"]][["commodity", "month", "price"]]
    rows = []
    for _, r in led.iterrows():
        if r["label"] == "MONITOR" or not np.isfinite(r.get("exp_move_3m", np.nan)):
            continue
        o = obs[obs["commodity"] == r["commodity"]]
        target = r["asof"] + pd.DateOffset(months=3)
        lo = r["asof"] + pd.DateOffset(months=window_m[0])
        hi = r["asof"] + pd.DateOffset(months=window_m[1])
        cand = o[(o["month"] >= lo) & (o["month"] <= hi)]
        if cand.empty:
            continue                                   # not matured yet
        idx = (cand["month"] - target).abs().idxmin()
        matured_price = float(cand.loc[idx, "price"])
        matured_month = cand.loc[idx, "month"]
        p0 = float(r["last_price"])
        realized = (matured_price - p0) / p0
        exp = float(r["exp_move_3m"])
        flat = abs(realized) <= DECISION_BAND
        correct = flat or (np.sign(realized) == np.sign(exp))

        qty = r["stake_qty"] if np.isfinite(r.get("stake_qty", np.nan)) else 0.0
        if r["label"] in BUY_FAMILY:
            follow_gain = (matured_price - p0) * qty       # bought early
        elif r["label"] in WAIT_FAMILY:
            follow_gain = (p0 - matured_price) * qty       # deferred
        else:
            follow_gain = 0.0
        rows.append(dict(
            asof=r["asof"], commodity=r["commodity"], label=r["label"],
            exp_move_3m=exp, realized_move=realized,
            price_at_signal=p0, matured_price=matured_price,
            matured_month=matured_month, stake_qty=qty,
            direction_correct=bool(correct),
            follow_gain=float(follow_gain)))
    df = pd.DataFrame(rows)
    if len(df):
        df = df.sort_values("matured_month").reset_index(drop=True)
        df["cumulative_gain"] = df["follow_gain"].cumsum()
    return df


# -------------------------------------------------------- 3. held-out hindsight
def hindsight_from_backtest(monthly: pd.DataFrame,
                            test_preds: pd.DataFrame,
                            champions: pd.DataFrame) -> dict:
    """Replay the untouched 20% test window as timing decisions.

    At each test step the buyer must cover that month's actual tonnage and
    can either lock immediately at the last known price or buy on schedule
    at the (then-unknown) test-month price. The champion's forecast makes
    the call. Scored against always-lock, always-wait, and perfect foresight.
    """
    champ_map = champions.set_index("commodity")["model"].to_dict()
    obs = monthly[monthly["observed"]].sort_values(["commodity", "month"])
    events = []
    for com, g in test_preds.groupby("commodity"):
        model = champ_map.get(com)
        t = g[g["model"] == model].sort_values("month")
        if t.empty:
            continue
        series = obs[obs["commodity"] == com].reset_index(drop=True)
        pos = {m: i for i, m in enumerate(series["month"])}
        for _, r in t.iterrows():
            i = pos.get(r["month"])
            if i is None or i == 0 or not np.isfinite(r["pred"]):
                continue
            prev_price = float(series.loc[i - 1, "price"])
            qty = float(series.loc[i, "qty"]) or 0.0
            actual = float(r["actual"])
            rel = (r["pred"] - prev_price) / prev_price
            if rel > DECISION_BAND:
                call, cost_follow = "buy early", prev_price
            elif rel < -DECISION_BAND:
                call, cost_follow = "wait", actual
            else:
                call, cost_follow = "neutral", actual
            events.append(dict(
                commodity=com, month=r["month"], horizon=int(r["horizon"]),
                qty=qty, prev_price=prev_price, actual_price=actual,
                predicted=float(r["pred"]), call=call,
                went_up=actual > prev_price,
                cost_follow=cost_follow * qty,
                cost_always_early=prev_price * qty,
                cost_always_wait=actual * qty,
                cost_perfect=min(prev_price, actual) * qty))
    ev = pd.DataFrame(events)
    if ev.empty:
        return dict(events=ev)
    decided = ev[ev["call"] != "neutral"].copy()
    correct = ((decided["call"] == "buy early") & decided["went_up"]) | \
              ((decided["call"] == "wait") & ~decided["went_up"])
    decided["correct"] = correct
    tot = dict(
        events=ev, decided=decided,
        n_events=int(len(ev)), n_decided=int(len(decided)),
        hit_rate=float(correct.mean()) if len(decided) else np.nan,
        cost_follow=float(ev["cost_follow"].sum()),
        cost_always_early=float(ev["cost_always_early"].sum()),
        cost_always_wait=float(ev["cost_always_wait"].sum()),
        cost_perfect=float(ev["cost_perfect"].sum()),
    )
    tot["saved_vs_early"] = tot["cost_always_early"] - tot["cost_follow"]
    tot["saved_vs_wait"] = tot["cost_always_wait"] - tot["cost_follow"]
    best_naive = min(tot["cost_always_early"], tot["cost_always_wait"])
    tot["saved_vs_best_naive"] = best_naive - tot["cost_follow"]
    span = best_naive - tot["cost_perfect"]
    tot["foresight_capture"] = float(
        (best_naive - tot["cost_follow"]) / span) if span > 0 else np.nan
    # per-month cumulative advantage vs best naive habit
    ev["_adv"] = np.minimum(ev["cost_always_early"], ev["cost_always_wait"]) \
        - ev["cost_follow"]
    tl = ev.groupby("month", as_index=False)["_adv"].sum().sort_values("month")
    tl["cumulative"] = tl["_adv"].cumsum()
    tot["timeline"] = tl
    return tot
