# DSP Commodity Intelligence

**Intelligent Commodity Price Prediction & Procurement Decision Engine**
SAIL — Durgapur Steel Plant · Pravartanam (SAIL Digital Transformation)

A Streamlit application that turns eleven-and-a-half years of real purchase-order
history (21,441 PO lines, 5,698 materials, Feb 2015 → Jul 2026) into forecast-backed
buy/wait verdicts, negotiation bands and inventory timing for the person sitting at
the negotiation table.

## What's inside

| Piece | What it does |
|---|---|
| `src/data_pipeline.py` | Cleans the SAP PO dump, resolves a trustworthy unit price per line (partial-delivery distortions corrected with visible provenance flags), builds monthly price series and the commodity catalog. Rejects go to a quarantine audit — never silently into models. |
| `src/models.py` | 19-model forecasting zoo: statistical methods written from first principles (naive, seasonal-naive, drift, moving average, SES, Holt, Holt-Winters, Theta, linear trend, ridge AR) plus scikit-learn ML forecasters on lag/seasonality features. |
| `src/ensemble.py` | 4 ensemble strategies incl. simulated-annealing-optimised weights (scipy `dual_annealing`). Weights are learned on an inner validation slice inside the training window only. |
| `src/backtest.py` | The referee: leakage-safe chronological walk-forward on an 80/20 split of *observed* months. Each step forecasts across the true gap to the next real PO. |
| `src/train_all.py` | Orchestrator with per-commodity checkpointing. Selects a champion per commodity, generates 12-month forecasts with empirical ~80% bands, and computes decision signals. |
| `src/decision_engine.py` | Mamdani fuzzy buy-timing verdict (12 rules, from scratch), game-theory-informed negotiation bands from the plant's own PO-vs-estimate record, classical EOQ / safety-stock / reorder mathematics with every assumption exposed as a dial. |
| `src/ingest.py` | Self-service data updates: validates an uploaded SAP export, merges it group-wise into the master (adds new lines, updates revised ones, never erases history, idempotent on re-upload), archives the file, and writes the append-only audit trail under `data/audit/`. |
| `src/impact.py` | The accountability engine: prospective value-at-stake, an append-only signal ledger snapshotted at every retrain, automatic verification of matured signals as actuals arrive, and a held-out replay scored against naive habits and perfect foresight. |
| `src/external_data.py` | Live global benchmarks (FRED keyless endpoint + optional yfinance) with disk caching. Never fabricates: if a fetch fails and no cache exists, the panel says so. |
| `app.py` | The dashboard (light theme, auto dark): Command Center with today's headline call, deep-dives with 3/6/12-month forecast tabs, Negotiation Room, Inventory Planner, **Impact Tracker** (money at stake now, a self-verifying signal ledger, and held-out proof of the track record), Market Pulse, Model Lab, a plain-language How-It-Works page with live accuracy, and the drag-and-drop Admin update flow. |
| `notebooks/01_model_laboratory.ipynb` | The executed audit trail — every output produced by genuinely running the code against the real workbook. |

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py          # artifacts are pre-computed and committed
```

Refresh with new data the easy way: open **Admin — Data & Retraining** in the
app and drag & drop the latest SAP export. The portal validates it, merges it
(new lines added, revised lines updated, history never erased, duplicate
uploads ignored), re-referees only the affected commodities, and logs the
whole event — who, when, what changed, file SHA-256 — to the audit trail
shown on the same page.

Command-line full rebuild remains available:

```bash
python -m src.train_all --refresh     # ~20 minutes; checkpointed, resumable
python smoke_test.py                  # verify before launching
```

Champion re-selection against fresh data is the self-learning loop.

## Honesty guarantees

- Model accuracy is scored only against months containing a real purchase,
  with strictly past-only information at every step.
- Ensemble weights never see the test window.
- Forecast bands are the champion's own held-out error distribution, not a
  formula's promise.
- Every corrected price carries a provenance flag; every rejected line is in
  `data/processed/quarantine_audit`.
- Every data upload is fingerprinted, archived, and audit-logged; merges are
  idempotent and can never delete history.
- The external-indices panel shows live/cached/unavailable status per series
  and will display an honest empty state rather than an invented number.

## Deployment

See `docs/DSP_Commodity_Intelligence_Deployment_Guide.docx` for the
step-by-step GitHub → Streamlit Community Cloud walkthrough (private repo,
free tier), plus local and plant-network options.

*Data note: keep this repository **private** — it contains real procurement data.*
