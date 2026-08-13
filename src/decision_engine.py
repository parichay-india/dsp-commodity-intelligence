"""
Decision layer of the DSP Commodity Intelligence engine.

Three cooperating components, all fully transparent:

1.  A Mamdani fuzzy-inference system (implemented from first principles)
    that fuses forecast direction, price momentum, ordering urgency and
    volatility into a single 0-100 buy-timing score with plain-English
    reasons — soft computing doing what it does best: turning several
    fuzzy truths into one defensible verdict.

2.  A negotiation-band builder grounded in the plant's own negotiation
    record (PO price vs PR estimate distributions, tender-mode
    competitiveness) and the price forecast — a game-theory-informed
    heuristic for open / target / walk-away anchors, quote percentiles
    and the cost of waiting one procurement cycle.

3.  Classical inventory mathematics (EOQ, safety stock, reorder timing)
    driven by the consumption pattern visible in receipts. Lead time,
    service level, ordering and carrying costs are explicit, adjustable
    assumptions — never silent hard-codes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

Z_TABLE = {0.90: 1.2816, 0.95: 1.6449, 0.975: 1.96, 0.99: 2.3263}


# ================================================================ fuzzy machinery
def _trap(x, a, b, c, d):
    """Trapezoidal membership; degenerate to triangle when b == c."""
    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if x < b:
        return (x - a) / max(b - a, 1e-9)
    return (d - x) / max(d - c, 1e-9)


# input membership definitions
MOVE = {   # expected % change over the decision horizon
    "falling": lambda x: _trap(x, -1.0, -1.0, -0.06, -0.02),
    "flat":    lambda x: _trap(x, -0.05, -0.015, 0.015, 0.05),
    "rising":  lambda x: _trap(x, 0.02, 0.06, 1.0, 1.0),
}
MOM = {    # recent observed monthly slope (relative)
    "down": lambda x: _trap(x, -1.0, -1.0, -0.03, -0.008),
    "flat": lambda x: _trap(x, -0.02, -0.006, 0.006, 0.02),
    "up":   lambda x: _trap(x, 0.008, 0.03, 1.0, 1.0),
}
URG = {    # months since last PO / median cycle
    "low":  lambda x: _trap(x, -1.0, -1.0, 0.45, 0.75),
    "med":  lambda x: _trap(x, 0.55, 0.85, 1.05, 1.35),
    "high": lambda x: _trap(x, 1.05, 1.4, 99.0, 99.0),
}
VOL = {    # coefficient of variation, last 12 observed prices
    "low":  lambda x: _trap(x, -1.0, -1.0, 0.03, 0.07),
    "high": lambda x: _trap(x, 0.10, 0.16, 9.0, 9.0),
}

# output fuzzy sets on the 0-100 buy-score axis
OUT = {
    "strong_wait": (0, 0, 12, 28),
    "wait":        (18, 30, 38, 48),
    "neutral":     (42, 50, 50, 58),
    "buy":         (52, 62, 70, 80),
    "strong_buy":  (72, 86, 100, 100),
}

RULES = [
    # (move, momentum, urgency, vol) -> (output, weight, reason)
    (("rising", None, "high", None), "strong_buy", 1.0,
     "Prices expected to rise and the ordering cycle is overdue — cover now."),
    (("rising", None, "med", None), "buy", 1.0,
     "Upward price outlook with a due-soon ordering cycle — buy ahead of the rise."),
    (("rising", None, "low", None), "buy", 0.8,
     "No urgency yet, but locking volume before a forecast rise protects cost."),
    (("falling", None, "low", None), "strong_wait", 1.0,
     "Prices expected to soften and stock position allows waiting."),
    (("falling", None, "med", None), "wait", 1.0,
     "Softening outlook — defer to late in the cycle to capture the drop."),
    (("falling", None, "high", None), "neutral", 1.0,
     "Stock is due but prices are easing — stagger purchases in smaller lots."),
    (("flat", None, "high", None), "buy", 1.0,
     "Stable prices and an overdue cycle — replenish at prevailing rates."),
    (("flat", None, "med", None), "neutral", 0.9,
     "Stable prices, normal cycle position — proceed on routine timing."),
    (("flat", None, "low", None), "wait", 0.8,
     "Stable prices with comfortable cover — no reason to advance the buy."),
    (("rising", "up", None, None), "strong_buy", 0.7,
     "Forecast and recent momentum both point up — reinforced buy timing."),
    (("falling", "down", None, None), "strong_wait", 0.7,
     "Forecast and recent momentum both point down — reinforced wait."),
    ((None, None, None, "high"), "neutral", 0.5,
     "High price volatility — favour staggered lots over one large bet."),
]


def fuzzy_buy_signal(exp_move: float, momentum: float, urgency: float,
                     volatility: float) -> dict:
    """Mamdani inference with max aggregation and centroid defuzzification."""
    mu_in = {
        "move": {k: f(exp_move) for k, f in MOVE.items()},
        "mom": {k: f(momentum) for k, f in MOM.items()},
        "urg": {k: f(urgency) for k, f in URG.items()},
        "vol": {k: f(volatility) for k, f in VOL.items()},
    }
    xs = np.linspace(0, 100, 201)
    agg = np.zeros_like(xs)
    fired = []
    for (m, mo, u, v), out, w, reason in RULES:
        strength = w
        for val, dim in ((m, "move"), (mo, "mom"), (u, "urg"), (v, "vol")):
            if val is not None:
                strength = min(strength, mu_in[dim][val])
        if strength <= 0.01:
            continue
        a, b, c, d = OUT[out]
        clipped = np.minimum([_trap(x, a, b, c, d) for x in xs], strength)
        agg = np.maximum(agg, clipped)
        fired.append((strength, reason))
    if agg.sum() < 1e-9:
        score = 50.0
    else:
        score = float(np.sum(xs * agg) / np.sum(agg))
    fired.sort(reverse=True)
    if score >= 72:
        label, colour = "BUY NOW", "#16a34a"
    elif score >= 58:
        label, colour = "BUY / STAGGER", "#65a30d"
    elif score >= 42:
        label, colour = "MONITOR", "#d97706"
    elif score >= 28:
        label, colour = "WAIT", "#ea580c"
    else:
        label, colour = "HOLD OFF", "#dc2626"
    return dict(score=round(score, 1), label=label, colour=colour,
                reasons=[r for _, r in fired[:3]],
                inputs=dict(exp_move=exp_move, momentum=momentum,
                            urgency=urgency, volatility=volatility))


# ============================================================= negotiation module
POWER_BY_MODE = [
    ("LTE-MULTI", 0.80), ("OT / GTE", 0.85), ("GEM", 0.80), ("IPT", 0.70),
    ("RATE CONTRACT", 0.55), ("DGSD", 0.55), ("ST(", 0.35), ("PAC", 0.30),
]


def bargaining_power(dominant_mode: str) -> float:
    """Competitive tenders → strong buyer position; single tender → weak."""
    mode = (dominant_mode or "").upper()
    for key, p in POWER_BY_MODE:
        if key in mode:
            return p
    return 0.6


def negotiation_bands(obs_prices: pd.DataFrame, forecast: dict,
                      ratio_q25: float, ratio_q75: float,
                      dominant_mode: str) -> dict:
    """obs_prices: observed months of one commodity (month, price, qty)."""
    recent = obs_prices.tail(6)
    w = recent["qty"].clip(lower=0).replace(0, np.nan).fillna(1.0)
    ref = float(np.average(recent["price"], weights=w))
    p50 = forecast.get("p50_3", ref)
    p10 = forecast.get("p10_3", ref * 0.95)
    p90 = forecast.get("p90_3", ref * 1.05)

    target = float(np.clip(0.5 * ref + 0.5 * p50, p10, p90))
    q25 = ratio_q25 if np.isfinite(ratio_q25) else 0.97
    q75 = ratio_q75 if np.isfinite(ratio_q75) else 1.03
    open_price = target * float(min(q25, 0.97))
    walk_away = float(min(p90, ref * max(q75, 1.02)) )
    walk_away = max(walk_away, target * 1.01)
    power = bargaining_power(dominant_mode)
    return dict(reference=ref, open=open_price, target=target,
                walk_away=walk_away, power=power,
                forecast_p50=p50, forecast_p10=p10, forecast_p90=p90)


def assess_quote(quote: float, qty: float, bands: dict,
                 hist_prices: np.ndarray, p50_next_cycle: float) -> dict:
    hist = hist_prices[np.isfinite(hist_prices)]
    pct = float((hist <= quote).mean() * 100) if len(hist) else np.nan
    power = bands["power"]
    # game-theory-informed counter: concede from open toward the quote in
    # proportion to the seller's leverage (1 - buyer power), capped at target
    concession = (1 - power) * 0.5
    counter = bands["open"] + concession * (min(quote, bands["walk_away"]) - bands["open"])
    counter = float(min(counter, bands["target"]))
    wait_gain = float((quote - p50_next_cycle) * qty)  # >0 means waiting looks cheaper
    if quote <= bands["target"]:
        verdict, colour = "ACCEPTABLE — at or under target", "#16a34a"
    elif quote <= bands["walk_away"]:
        verdict, colour = "NEGOTIATE — between target and walk-away", "#d97706"
    else:
        verdict, colour = "REJECT / RE-TENDER — above walk-away", "#dc2626"
    return dict(quote=quote, percentile=pct, counter=counter,
                verdict=verdict, colour=colour, wait_gain=wait_gain,
                target=bands["target"], walk_away=bands["walk_away"],
                open=bands["open"])


# =============================================================== inventory module
def inventory_plan(monthly: pd.DataFrame, last_po: pd.Timestamp,
                   median_gap_days: float, p90_gap_days: float,
                   unit_price: float, asof: pd.Timestamp,
                   lead_time_m: float = 1.0, service: float = 0.95,
                   order_cost: float = 25000.0, carry_rate: float = 0.20) -> dict:
    """Consumption proxied by receipts; every economic input is an argument."""
    win = monthly.tail(36)
    d_m = float(win["qty"].mean())              # monthly demand rate
    sd_m = float(win["qty"].std(ddof=0))
    active = win[win["qty"] > 0]
    z = Z_TABLE.get(round(service, 3), 1.6449)

    d_year = d_m * 12
    hold = max(carry_rate * unit_price, 1e-9)
    eoq = float(np.sqrt(2 * d_year * order_cost / hold)) if d_year > 0 else np.nan
    safety = float(z * sd_m * np.sqrt(max(lead_time_m, 1e-9)))
    rop_qty = float(d_m * lead_time_m + safety)
    cycle_m = (median_gap_days / 30.44) if np.isfinite(median_gap_days) else np.nan
    eoq_cycle_m = float(eoq / d_m) if d_m > 0 and np.isfinite(eoq) else np.nan

    months_since = (asof - last_po).days / 30.44 if pd.notna(last_po) else np.nan

    # --- stock-cover estimate from receipt flow (no stock ledger in SAP
    # export, so cover = last replenishment ÷ trailing consumption rate,
    # drawn down since the last receipt; labelled an estimate everywhere)
    last_event_qty = float(active["qty"].iloc[-1]) if len(active) else np.nan
    cover_total_m = (last_event_qty / d_m) if d_m > 0 and \
        np.isfinite(last_event_qty) else np.nan
    cover_left_m = (cover_total_m - months_since) if np.isfinite(cover_total_m) \
        and np.isfinite(months_since) else np.nan
    stockout_date = (last_po + pd.Timedelta(days=cover_total_m * 30.44)) \
        if pd.notna(last_po) and np.isfinite(cover_total_m) else pd.NaT
    po_by_consumption = (stockout_date - pd.Timedelta(days=lead_time_m * 30.44)) \
        if pd.notna(stockout_date) else pd.NaT

    overdue_hist = np.isfinite(months_since) and np.isfinite(p90_gap_days) \
        and months_since * 30.44 > p90_gap_days
    if (np.isfinite(cover_left_m) and cover_left_m <= 0) or overdue_hist:
        risk = "HIGH"
    elif (np.isfinite(cover_left_m) and cover_left_m <= lead_time_m) or (
            np.isfinite(months_since) and np.isfinite(median_gap_days)
            and months_since * 30.44 > median_gap_days):
        risk = "MEDIUM"
    else:
        risk = "LOW"
    next_by = (last_po + pd.Timedelta(days=median_gap_days - lead_time_m * 30.44)
               ) if pd.notna(last_po) and np.isfinite(median_gap_days) else pd.NaT
    return dict(demand_month=d_m, demand_sd=sd_m, active_months=int(len(active)),
                eoq=eoq, safety_stock=safety, reorder_point=rop_qty,
                order_cycle_hist_m=cycle_m, order_cycle_eoq_m=eoq_cycle_m,
                months_since_last=months_since, stockout_risk=risk,
                next_order_by=next_by,
                last_event_qty=last_event_qty,
                cover_total_m=cover_total_m, cover_left_m=cover_left_m,
                stockout_date=stockout_date,
                po_by_consumption=po_by_consumption,
                assumptions=dict(lead_time_m=lead_time_m, service=service,
                                 order_cost=order_cost, carry_rate=carry_rate))


# =========================================================== PO recommendation
def order_pattern(po_slice: pd.DataFrame) -> dict:
    """Historical ordering habit: usual next date and usual event quantity,
    straight from the commodity's own PO record (no models involved)."""
    g = po_slice.dropna(subset=["PO Date"]).copy()
    if g.empty:
        return dict(usual_next_date=pd.NaT, usual_qty=np.nan,
                    qty_p25=np.nan, qty_p75=np.nan, n_events=0,
                    median_gap_days=np.nan)
    ev = g.groupby(g["PO Date"].dt.normalize())["Quantity Received"] \
          .sum().sort_index()
    gaps = ev.index.to_series().diff().dt.days.dropna()
    med_gap = float(gaps.median()) if len(gaps) else np.nan
    last = ev.index.max()
    usual_next = last + pd.Timedelta(days=med_gap) if np.isfinite(med_gap) \
        else pd.NaT
    q = ev[ev > 0]
    return dict(usual_next_date=usual_next,
                usual_qty=float(q.median()) if len(q) else np.nan,
                qty_p25=float(q.quantile(.25)) if len(q) else np.nan,
                qty_p75=float(q.quantile(.75)) if len(q) else np.nan,
                n_events=int(len(ev)), median_gap_days=med_gap)


def ai_po_recommendation(plan: dict, pattern: dict, signal: dict,
                         asof: pd.Timestamp,
                         constraints: dict | None = None) -> dict:
    """AI-suggested next PO date and quantity.

    Date logic: start from the earlier of the two safety clocks (historical
    order-by and consumption-based order-by). A rising-price verdict pulls
    the order forward — BUY NOW to today, BUY/STAGGER halfway to today. A
    falling-price verdict lets it slide to the latest safe date so the drop
    is captured. Never later than the consumption clock allows, never
    before today.

    Quantity logic: anchor on EOQ. Rising prices extend coverage to the
    full historical cycle (buy ahead of the rise, capped at 1.5 cycles).
    Falling prices shrink the lot to bridge stock only (lead-time demand
    plus safety stock) so the balance is bought cheaper later. Historical
    p25–p75 event sizes act as sanity rails when available.
    """
    lt = plan["assumptions"]["lead_time_m"]
    label = signal["label"] if signal else "MONITOR"
    exp3 = float(signal.get("exp_move_3m", 0.0)) if signal else 0.0
    d_m = plan["demand_month"]
    cyc = pattern["median_gap_days"] / 30.44 \
        if np.isfinite(pattern["median_gap_days"]) else np.nan

    hist_by = (pattern["usual_next_date"] - pd.Timedelta(days=lt * 30.44)) \
        if pd.notna(pattern["usual_next_date"]) else pd.NaT
    cons_by = plan.get("po_by_consumption", pd.NaT)
    candidates = [d for d in (hist_by, cons_by) if pd.notna(d)]
    base = min(candidates) if candidates else asof
    latest_safe = cons_by if pd.notna(cons_by) else base

    reasons = []
    if label == "BUY NOW":
        date = asof
        reasons.append(f"Forecast {exp3*100:+.1f}% over 3m with high "
                       "urgency — place the order now.")
    elif label == "BUY / STAGGER":
        date = min(base, asof + (base - asof) / 2) if base > asof else asof
        reasons.append(f"Forecast {exp3*100:+.1f}% — advance the buy and "
                       "split lots rather than waiting for the usual date.")
    elif label in ("WAIT", "HOLD OFF"):
        date = latest_safe
        if pd.notna(latest_safe) and latest_safe <= asof:
            reasons.append(f"Prices point down ({exp3*100:+.1f}%), but the "
                           "consumption clock says cover is exhausted — "
                           "safety overrides the wait: order now, in a "
                           "trimmed lot, and buy the balance after the drop.")
        else:
            reasons.append(f"Forecast {exp3*100:+.1f}% — defer to the latest "
                           "safe date so the expected drop is captured.")
    else:
        date = base
        reasons.append("No strong price direction — keep the routine "
                       "timing, safety clocks govern.")
    if pd.notna(latest_safe):
        date = min(date, latest_safe)
    date = max(date, asof)

    eoq = plan["eoq"] if np.isfinite(plan.get("eoq", np.nan)) else np.nan
    bridge = d_m * lt + plan["safety_stock"] if d_m > 0 else np.nan
    if label in ("BUY NOW", "BUY / STAGGER") and np.isfinite(cyc) and d_m > 0:
        qty = max(eoq if np.isfinite(eoq) else 0.0, d_m * cyc)
        qty = min(qty, d_m * cyc * 1.5)
        reasons.append("Quantity covers the full cycle ahead of the rise "
                       "(EOQ floor, 1.5-cycle cap).")
    elif label in ("WAIT", "HOLD OFF") and np.isfinite(bridge):
        qty = bridge
        reasons.append("Quantity trimmed to bridge stock (lead-time demand "
                       "+ safety) — buy the balance cheaper later.")
    else:
        qty = eoq if np.isfinite(eoq) else (d_m * cyc if np.isfinite(cyc)
                                            and d_m > 0 else np.nan)
        reasons.append("Quantity at the economic order size.")
    if np.isfinite(pattern.get("qty_p75", np.nan)) and np.isfinite(qty):
        hi_rail = pattern["qty_p75"] * 1.5
        if qty > hi_rail:
            qty = hi_rail
            reasons.append("Capped at 1.5× the historical p75 event size.")

    # ---- user constraints: MOQ floor, per-PO maximum, holding capacity
    c = constraints or {}
    moq = c.get("moq", np.nan)
    max_oq = c.get("max_oq", np.nan)
    cap = c.get("holding_cap", np.nan)
    n_lots = 1
    if np.isfinite(qty):
        if np.isfinite(moq) and qty < moq:
            qty = moq
            reasons.append(f"Lifted to the vendor MOQ of {moq:,.0f}.")
        if np.isfinite(max_oq) and qty > max_oq:
            n_lots = int(np.ceil(qty / max_oq))
            reasons.append(f"Total exceeds the per-PO maximum of "
                           f"{max_oq:,.0f} — split into {n_lots} lots "
                           "(see the staggered plan below).")
        if np.isfinite(cap):
            on_hand = max(plan.get("cover_left_m", 0.0), 0.0) * d_m \
                if np.isfinite(plan.get("cover_left_m", np.nan)) else 0.0
            headroom = cap - on_hand
            if qty > headroom:
                reasons.append(f"Holding capacity {cap:,.0f} leaves "
                               f"headroom ≈ {max(headroom, 0):,.0f} today — "
                               "receipts must be paced with consumption "
                               "(the staggered plan does this).")
                n_lots = max(n_lots, 2)
    return dict(date=date, qty=float(qty) if np.isfinite(qty) else np.nan,
                label=label, reasons=reasons, latest_safe=latest_safe,
                n_lots=n_lots,
                constraints_used=dict(moq=moq, max_oq=max_oq,
                                      holding_cap=cap))


# ============================================================ stagger planner
def build_stagger_plan(plan: dict, pattern: dict, signal: dict,
                       forecast_df: pd.DataFrame, asof: pd.Timestamp,
                       total_qty: float, constraints: dict | None = None,
                       max_tranches: int = 6) -> dict:
    """Turn a total requirement into a concrete tranche schedule.

    The whole intelligence is one rule applied per tranche: compute its
    feasibility window — earliest arrival = first month where holding
    capacity can absorb the lot (given projected drawdown) and the lead
    time has passed; latest arrival = last month before stock would run
    out — then buy at the CHEAPEST champion-forecast price inside that
    window. Rising forecasts naturally pull tranches early, falling ones
    push them late, dips get caught; MOQ, per-PO maximum and capacity
    shape lot sizes throughout. Monthly granularity, stated as such.
    """
    c = constraints or {}
    d = float(plan.get("demand_month", np.nan))
    lt_m = float(plan["assumptions"]["lead_time_m"])
    m_lead = max(int(round(lt_m)), 0)
    if not (np.isfinite(total_qty) and total_qty > 0 and np.isfinite(d)
            and d > 0):
        return dict(rows=pd.DataFrame(), summary=dict(
            note="No plan — demand rate or requirement unavailable."))

    lot_min = c.get("moq", np.nan)
    lot_max = c.get("max_oq", np.nan)
    cap = c.get("holding_cap", np.nan)
    lot_min = lot_min if np.isfinite(lot_min) else 0.0
    lot_max = lot_max if np.isfinite(lot_max) else np.inf
    cap = cap if np.isfinite(cap) else np.inf

    on_hand0 = max(plan.get("cover_left_m", 0.0), 0.0) * d \
        if np.isfinite(plan.get("cover_left_m", np.nan)) else 0.0
    last_price = float(signal["last_price"]) if signal else np.nan
    fc = forecast_df.set_index("horizon")["p50"] if len(forecast_df) \
        else pd.Series(dtype=float)

    def price(m: int) -> float:
        if m <= 0 or fc.empty:
            return last_price
        if m in fc.index:
            return float(fc.loc[m])
        return float(fc.loc[min(fc.index.max(), max(fc.index.min(), m))])

    H = min(int(np.ceil((on_hand0 + total_qty) / d)) + m_lead + 2, 15)
    arrivals: list[tuple[int, float]] = []

    def stock_before(m: int) -> float:
        return on_hand0 - d * m + sum(q for a, q in arrivals if a < m)

    rows, warn = [], []
    R = total_qty
    t = 0
    while R > 1e-9 and t < max_tranches:
        t += 1
        lot = min(R, lot_max)
        moq_note = ""
        if lot < lot_min:
            if rows and rows[-1]["qty"] + R <= lot_max + 1e-9:
                rows[-1]["qty"] += R
                rows[-1]["why"] += (" Remainder folded in (below MOQ as a "
                                    "separate lot).")
                arrivals[-1] = (arrivals[-1][0], rows[-1]["qty"])
                R = 0.0
                break
            extra = lot_min - lot
            lot = lot_min
            moq_note = (f" Rounded up to MOQ {lot_min:,.0f} "
                        f"(+{extra:,.0f} beyond requirement).")
        prev_a = arrivals[-1][0] if arrivals else -1
        e = max(m_lead, prev_a + 1)
        cap_note = ""
        while e <= H and stock_before(e) + lot > cap + 1e-6:
            e += 1
        if e > H:
            head = max(cap - stock_before(max(m_lead, prev_a + 1)), 0.0)
            if head >= max(lot_min, 1e-9):
                lot, e = head, max(m_lead, prev_a + 1)
                cap_note = (f" Lot trimmed to capacity headroom "
                            f"{head:,.0f}.")
            else:
                warn.append(f"{R:,.0f} could not be scheduled — capacity "
                            "leaves no usable headroom in the horizon.")
                break
        if e > max(m_lead, prev_a + 1):
            cap_note += (f" Earliest receipt pushed to month {e} by "
                         "holding capacity.")
        latest = e
        m = e + 1
        while m <= H and stock_before(m) > -1e-6:
            latest = m
            m += 1
        squeeze = ""
        if latest < e:
            latest, squeeze = e, (" Window squeezed — stock runs out "
                                  "before capacity frees; expedite.")
        elif latest == e and rows and stock_before(e) < -1e-6:
            squeeze = (" Back-to-back with the previous lot — demand "
                       "outruns the per-PO maximum until stock rebuilds.")
        window = range(e, latest + 1)
        m_star = min(window, key=lambda mm: (price(mm), mm))
        gap_note = ""
        if not rows and stock_before(m_star) < -1e-6:
            gap_note = (" Cover runs out before this first receipt can "
                        "land (lead time) — expedite or bridge from "
                        "stores.")
            warn.append("Estimated cover is exhausted before the earliest "
                        "possible receipt; the schedule starts at the lead-"
                        "time boundary.")
        why = (f"Cheapest forecast point (₹{price(m_star):,.0f}) in its "
               f"month {e}–{latest} feasibility window.")
        rows.append(dict(order_m=max(m_star - m_lead, 0), arrive_m=m_star,
                         qty=lot, price=price(m_star),
                         why=why + cap_note + moq_note + squeeze
                         + gap_note))
        arrivals.append((m_star, lot))
        R -= lot
        R = max(R, 0.0)

    if R > 1e-9:
        warn.append(f"{R:,.0f} of the requirement remains unscheduled "
                    f"within {max_tranches} tranches — raise the per-PO "
                    "maximum or holding capacity.")

    if not rows:
        return dict(rows=pd.DataFrame(), summary=dict(
            note="; ".join(warn) or "No tranches needed."))

    out = pd.DataFrame(rows)
    out["order_by"] = out["order_m"].apply(
        lambda k: asof + pd.DateOffset(months=int(k)))
    out["arrives"] = out["arrive_m"].apply(
        lambda k: asof + pd.DateOffset(months=int(k)))
    out["share"] = out["qty"] / out["qty"].sum()
    out["est_cost"] = out["qty"] * out["price"]
    covers = []
    for i, r in out.iterrows():
        s = (on_hand0 - d * r["arrive_m"]
             + sum(q for a, q in arrivals[: i + 1]))
        covers.append(max(s, 0.0) / d)
    out["cover_after_m"] = covers
    out.insert(0, "tranche", range(1, len(out) + 1))

    total_lots = float(out["qty"].sum())
    cost_stag = float(out["est_cost"].sum())
    cost_now = total_lots * price(m_lead)
    breach = " (would breach holding capacity)" \
        if on_hand0 + total_lots > cap + 1e-6 else ""
    usual_m = m_lead
    if pd.notna(pattern.get("usual_next_date")):
        usual_m = max(int(round(
            (pattern["usual_next_date"] - asof).days / 30.44)) + m_lead,
            m_lead)
    cost_usual = total_lots * price(min(usual_m, H))
    summary = dict(total_qty=total_lots, est_cost=cost_stag,
                   cost_all_now=cost_now, cost_all_now_note=breach,
                   cost_all_usual=cost_usual,
                   vs_all_now=cost_now - cost_stag,
                   vs_all_usual=cost_usual - cost_stag,
                   warnings=warn)
    cols = ["tranche", "order_by", "arrives", "qty", "share", "price",
            "est_cost", "cover_after_m", "why"]
    return dict(rows=out[cols], summary=summary)


# =========================================================== signal computation
def compute_signal(obs: pd.DataFrame, fc: dict, cat_row: pd.Series,
                   asof: pd.Timestamp) -> dict:
    """Everything the Action Board needs for one commodity."""
    prices = obs["price"].to_numpy(float)
    last_price = prices[-1]
    exp3 = (fc.get("p50_3", last_price) - last_price) / last_price
    exp6 = (fc.get("p50_6", last_price) - last_price) / last_price
    exp12 = (fc.get("p50_12", last_price) - last_price) / last_price

    tail = obs.tail(6)
    if len(tail) >= 3:
        mi = (tail["month"].dt.year * 12 + tail["month"].dt.month).to_numpy(float)
        slope = np.polyfit(mi - mi[0], np.log(tail["price"].to_numpy(float)), 1)[0]
    else:
        slope = 0.0
    vol = float(pd.Series(prices[-12:]).std() / pd.Series(prices[-12:]).mean()) \
        if len(prices) >= 4 else 0.05

    cycle_m = cat_row["median_order_gap_days"] / 30.44 \
        if np.isfinite(cat_row["median_order_gap_days"]) else 3.0
    months_since = (asof - cat_row["last_po"]).days / 30.44
    urgency = months_since / max(cycle_m, 0.5)

    sig = fuzzy_buy_signal(exp3, float(slope), float(urgency), vol)
    sig.update(exp_move_3m=exp3, exp_move_6m=exp6, exp_move_12m=exp12,
               momentum=float(slope), volatility=vol, urgency=float(urgency),
               months_since_last=float(months_since), cycle_months=float(cycle_m),
               last_price=float(last_price))
    return sig
