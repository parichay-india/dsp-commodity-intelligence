"""
Deployment smoke test — run `python smoke_test.py` after cloning or
retraining. Exercises every code path the dashboard calls, using the exact
signatures in app.py, without needing Streamlit itself.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import dashboard_data as dd
from src.data_pipeline import PROC
from src.decision_engine import assess_quote, inventory_plan, negotiation_bands

FAIL = []


def check(name, fn):
    try:
        fn()
        print(f"  OK   {name}")
    except Exception as e:
        FAIL.append((name, e))
        print(f"  FAIL {name}: {e}")


print("DSP Commodity Intelligence — smoke test\n")

check("artifacts present", lambda: (_ for _ in ()).throw(RuntimeError(
    "run `python -m src.train_all` first")) if not dd.artifacts_ready() else None)

B = dd.load_bundle()
print(f"  ..   {B['summary']['rows_priced']:,} priced PO lines, "
      f"{B['summary']['commodities_modelable']} modelled commodities, "
      f"as of {B['asof']:%d %b %Y}\n")

check("action board", lambda: dd.action_board(B).pipe(
    lambda d: None if len(d) > 50 else (_ for _ in ()).throw(RuntimeError("thin board"))))
check("kpis", lambda: dd.kpis(B))

board = dd.action_board(B)
sample = list(board["commodity"].head(5)) + list(board["commodity"].tail(2))
for com in sample:
    def one(com=com):
        P = dd.commodity_pack(B, com)
        sig, cat, obs = P["signal"], P["cat"], P["obs"]
        assert sig and len(obs) >= 12 and len(P["forecast"]) == 12
        bands = negotiation_bands(obs, sig["forecast"],
                                  sig.get("ratio_q25") or np.nan,
                                  sig.get("ratio_q75") or np.nan,
                                  cat["dominant_mode"])
        assert bands["open"] <= bands["target"] <= bands["walk_away"]
        fc = P["forecast"].set_index("horizon")
        cyc = max(int(round(sig["cycle_months"])), 1)
        res = assess_quote(bands["target"] * 1.02, 100.0, bands,
                           obs["price"].to_numpy(float),
                           float(fc.loc[min(cyc, 12), "p50"]))
        assert np.isfinite(res["counter"]) and 0 <= res["percentile"] <= 100
        plan = inventory_plan(P["filled"], cat["last_po"],
                              cat["median_order_gap_days"],
                              cat["p90_order_gap_days"],
                              sig["last_price"], B["asof"],
                              1.0, 0.95, 25000.0, 0.20)
        assert plan["stockout_risk"] in ("LOW", "MEDIUM", "HIGH")
        for key in ("cover_total_m", "cover_left_m", "stockout_date",
                    "po_by_consumption", "last_event_qty"):
            assert key in plan
        _ = dd.seasonality_matrix(obs)
    check(f"full pack · {com[:44]}", one)

check("champions readable", lambda: pd.read_json(
    PROC / "champions.jsonl", lines=True).pipe(
    lambda d: None if d["model"].notna().all() else
    (_ for _ in ()).throw(RuntimeError("null champion"))))

check("leaderboard/test-preds join", lambda: (
    None if set(pd.read_csv(PROC / "leaderboard.csv")["commodity"]) ==
    set(pd.read_csv(PROC / "test_predictions.csv")["commodity"])
    else (_ for _ in ()).throw(RuntimeError("mismatch"))))


def _ingest_checks():
    from src.ingest import fingerprint, merge_master, validate_workbook
    master = Path(__file__).resolve().parent / "data" / "raw" / \
        "DATA_COMMODITY__PRICING.XLSX"
    v = validate_workbook(master)
    assert v["ok"], v["issues"]
    assert len(fingerprint(master.read_bytes())) == 64
    stats = merge_master(v["df"], master, write=False)   # dry run, no writes
    assert stats["rows_added"] == 0 and stats["rows_updated"] == 0, \
        "master should merge into itself as a no-op"


check("ingest: validate + idempotent dry-run merge", _ingest_checks)


def _impact_checks():
    from src.impact import (evaluate_matured, hindsight_from_backtest,
                            read_ledger, snapshot_signals, value_on_table)
    champs = pd.read_json(PROC / "champions.jsonl", lines=True)
    vt = value_on_table(B["signals"], B["catalog"])
    assert len(vt) > 20 and vt["at_stake"].ge(0).all()
    h = hindsight_from_backtest(B["monthly"], B["test_preds"], champs)
    assert 0 < h["hit_rate"] <= 1 and np.isfinite(h["saved_vs_best_naive"])
    snapshot_signals()
    assert snapshot_signals() == 0, "snapshot must be idempotent per as-of"
    assert len(read_ledger()) >= 100
    evaluate_matured(B["monthly"])   # empty today; must not raise


check("impact: on-table + hindsight + ledger idempotency", _impact_checks)


def _external_checks():
    from src.external_data import INDEX_MAP, map_indices_to_commodities
    cat = B["catalog"][B["catalog"]["modelable"]]
    mp = map_indices_to_commodities(cat)
    assert len(mp) == len(INDEX_MAP)
    by = {m["index"]: m for m in mp}
    assert by["S&P GSCI commodity index"]["n_matched"] >= 5
    assert by["Dry-bulk freight (BDRY proxy)"]["n_matched"] >= 5
    assert any("GRAPHITE" in c for c in by["USD / INR"]["matched"])
    assert any("CABLE" in c or "WIRE" in c
               for c in by["Copper (USD/mt)"]["matched"])
    assert by["Nifty Metal (NSE)"]["region"] == "in"
    assert by["Nifty Metal (NSE)"]["n_matched"] >= 5
    assert "demand" in by["Nifty 50"]["how"]


check("external: index-to-commodity map", _external_checks)


def _constraint_checks():
    import numpy as np
    from src.constraints import (constraints_for, load_constraints,
                                 save_constraints, validate)
    from src.decision_engine import (ai_po_recommendation,
                                     build_stagger_plan, inventory_plan,
                                     order_pattern)
    com = "SILICO MANGANESE,25 TO 50 MM"
    P = dd.commodity_pack(B, com)
    plan = inventory_plan(P["filled"], P["cat"]["last_po"],
                          P["cat"]["median_order_gap_days"],
                          P["cat"]["p90_order_gap_days"],
                          P["signal"]["last_price"], B["asof"],
                          1.0, 0.95, 25000.0, 0.20)
    pat = order_pattern(P["po"])
    cons = dict(moq=2000.0, max_oq=4000.0, holding_cap=12000.0)
    ai = ai_po_recommendation(plan, pat, P["signal"], B["asof"], cons)
    assert ai["n_lots"] >= 2
    sp = build_stagger_plan(plan, pat, P["signal"], P["forecast"],
                            B["asof"], ai["qty"], cons)
    rows = sp["rows"]
    assert len(rows) >= 2
    assert (rows["qty"] <= cons["max_oq"] + 1e-6).all()
    assert (rows["qty"] >= cons["moq"] - 1e-6).all()
    assert rows["arrives"].is_monotonic_increasing
    assert abs(rows["qty"].sum() - ai["qty"]) <= cons["moq"] + 1
    bad = pd.DataFrame([dict(commodity="X", moq=100, max_oq=50,
                             holding_cap=40)])
    assert validate(bad), "validator must flag MOQ > max"


check("constraints + stagger planner", _constraint_checks)


def _registry_checks():
    from src.dashboard_data import (METHOD_NOTES, confidence_score,
                                    registry_frame)
    reg = registry_frame(B)
    assert len(reg) == B["summary"]["commodities_modelable"]
    assert reg["confidence"].between(0, 100).all()
    assert not (set(B["champions"]["model"]) - set(METHOD_NOTES))
    assert confidence_score(0.05, 0.6, 10) > confidence_score(0.20, 1.1, 4)


check("forecast registry + confidence", _registry_checks)

print()
if FAIL:
    print(f"{len(FAIL)} check(s) FAILED"); sys.exit(1)
print("All checks passed — the dashboard is safe to launch.")
