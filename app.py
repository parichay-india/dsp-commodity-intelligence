"""
Intelligent Commodity Price Prediction & Procurement Decision Engine
SAIL — Durgapur Steel Plant

Streamlit front end. All analytics live in src/ and are pre-computed by
`python -m src.train_all`; this file reads artifacts, draws the control
room, and runs the interactive decision mathematics.
"""

import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src import dashboard_data as dd
from src.data_pipeline import PROC, run_pipeline
from src.decision_engine import (assess_quote, inventory_plan,
                                 negotiation_bands)
from src.external_data import correlate, load_external

# ----------------------------------------------------------------- page & theme
st.set_page_config(page_title="DSP Commodity Intelligence",
                   page_icon="🔥", layout="wide",
                   initial_sidebar_state="expanded")

C = dict(
    bg="#F7F5F1", panel="#FFFFFF", panel2="#FBFAF7", line="#E5DFD6",
    text="#20262E", mute="#68727E", hot="#D4570F", amber="#B87400",
    good="#1E8E4E", warn="#B87400", bad="#C2352C", blue="#2E6FAE",
    heat_lo="#DCE9F5",
    gauge_zones=["#F6DEDC", "#F6E9D5", "#F4F0D6", "#E3EFDA", "#D8EEE2"],
)
SIGNAL_COLOURS = {"BUY NOW": "#1E8E4E", "BUY / STAGGER": "#5B9333",
                  "MONITOR": "#B87400", "WAIT": "#C2652C",
                  "HOLD OFF": "#C2352C"}

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
html, body, [class*="css"] {{ font-family: 'IBM Plex Sans', sans-serif; }}
.stApp {{ background: {C['bg']}; }}
h1,h2,h3 {{ color:{C['text']}; letter-spacing:.2px; }}
section[data-testid="stSidebar"] {{ background:{C['panel2']}; border-right:1px solid {C['line']}; }}
div[data-testid="stMetric"] {{ background:{C['panel']}; border:1px solid {C['line']};
  border-radius:10px; padding:14px 16px; }}
div[data-testid="stMetric"] label {{ color:{C['mute']}; }}
div[data-testid="stMetricValue"] {{ font-family:'IBM Plex Mono', monospace; color:{C['text']}; }}
div[data-testid="stDataFrame"] {{ background:#FFFFFF; border:1px solid {C['line']};
  border-radius:10px; padding:4px; }}
.verdict {{ border-radius:14px; padding:22px 26px; border:1px solid {C['line']};
  background:linear-gradient(160deg, {C['panel']} 0%, {C['panel2']} 100%); }}
.verdict .lbl {{ font-size:2.0rem; font-weight:700; font-family:'IBM Plex Mono',monospace; }}
.verdict .sub {{ color:{C['mute']}; margin-top:2px; }}
.chip {{ display:inline-block; padding:3px 12px; border-radius:20px;
  font-family:'IBM Plex Mono',monospace; font-size:.82rem; font-weight:600; }}
.reason {{ color:{C['text']}; background:{C['panel2']}; border-left:3px solid {C['hot']};
  padding:8px 12px; border-radius:6px; margin:6px 0; font-size:.92rem;
  border-top:1px solid {C['line']}; border-right:1px solid {C['line']};
  border-bottom:1px solid {C['line']}; }}
.hero {{ border-radius:14px; padding:16px 22px; margin: 4px 0 14px 0;
  border:1px solid {C['line']}; border-left:5px solid {C['hot']};
  background:linear-gradient(120deg, {C['panel']} 0%, {C['panel2']} 100%); }}
.smallnote {{ color:{C['mute']}; font-size:.85rem; }}
hr {{ border-color:{C['line']}; }}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------- formatting
def inr(x, unit=""):
    if x is None or not np.isfinite(x):
        return "—"
    a = abs(x)
    if a >= 1e7:
        return f"₹{x/1e7:,.2f} Cr{unit}"
    if a >= 1e5:
        return f"₹{x/1e5:,.2f} L{unit}"
    return f"₹{x:,.0f}{unit}"


def pct(x, signed=True):
    if x is None or not np.isfinite(x):
        return "—"
    s = "+" if (signed and x >= 0) else ""
    return f"{s}{x*100:.1f}%"


def plotly_base(fig, h=420, title=None):
    fig.update_layout(
        template=None, height=h, title=title,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=C["panel2"],
        font=dict(family="IBM Plex Sans", color=C["text"], size=13),
        margin=dict(l=10, r=10, t=48 if title else 24, b=10),
        legend=dict(orientation="h", y=1.06, x=0, bgcolor="rgba(0,0,0,0)"),
        transition=dict(duration=450, easing="cubic-in-out"),
        hoverlabel=dict(bgcolor=C["panel"], font_family="IBM Plex Mono"),
    )
    fig.update_xaxes(gridcolor=C["line"], zeroline=False)
    fig.update_yaxes(gridcolor=C["line"], zeroline=False)
    return fig


# ----------------------------------------------------------------- data loading
@st.cache_data(show_spinner="Loading intelligence artifacts…")
def get_bundle():
    return dd.load_bundle()


@st.cache_data(show_spinner=False)
def get_board(_stamp: str):
    return dd.action_board(get_bundle())


@st.cache_data(ttl=6 * 3600, show_spinner="Contacting market data sources…")
def get_external(insecure: bool = False, proxy: str = ""):
    return load_external(insecure=insecure, proxy=proxy or None)


@st.cache_data(show_spinner="Scoring the engine's track record…")
def get_impact(_stamp: str):
    from src.impact import (DECISION_BAND, evaluate_matured,
                            hindsight_from_backtest, read_ledger,
                            snapshot_signals, value_on_table)
    snapshot_signals()
    b = get_bundle()
    champs = pd.read_json(PROC / "champions.jsonl", lines=True)
    return dict(table=value_on_table(b["signals"], b["catalog"]),
                hindsight=hindsight_from_backtest(
                    b["monthly"], b["test_preds"], champs),
                matured=evaluate_matured(b["monthly"]),
                ledger=read_ledger())


DECISION_BAND_PCT = 1.5


def artifact_stamp():
    p = PROC / "decision_signals.json"
    return str(p.stat().st_mtime) if p.exists() else "none"


if not dd.artifacts_ready():
    st.title("🔥 DSP Commodity Intelligence")
    st.warning("Model artifacts not found. Run the training pipeline once, "
               "then reload this page.")
    st.code("python -m src.train_all", language="bash")
    st.markdown("Or open **⚙️ Admin — Data & Retraining** from the sidebar "
                "after placing the PO workbook under `data/raw/`.")
    st.stop()

B = get_bundle()
ASOF = B["asof"]

# ----------------------------------------------------------------- sidebar nav
st.sidebar.markdown(
    f"<div style='font-family:IBM Plex Mono,monospace;font-size:1.05rem;"
    f"font-weight:700;color:{C['hot']}'>SAIL • DURGAPUR STEEL PLANT</div>"
    f"<div style='color:{C['mute']};font-size:.85rem;margin-bottom:8px'>"
    f"Commodity Intelligence &nbsp;·&nbsp; data as of "
    f"<b>{ASOF:%d %b %Y}</b></div>", unsafe_allow_html=True)

PAGES = ["🏭 Command Center", "🔍 Commodity Deep-Dive", "🤝 Negotiation Room",
         "📦 Inventory Planner", "🏆 Impact Tracker", "🌐 Market Pulse",
         "🧪 Model Lab", "📚 Forecast Registry", "💡 How It Works",
         "⚙️ Admin — Data & Retraining"]
page = st.sidebar.radio("Navigate", PAGES,
                        index=PAGES.index(st.session_state.get("page", PAGES[0])))
st.session_state["page"] = page
st.sidebar.markdown("---")
st.sidebar.markdown(
    f"<span class='smallnote'>Pravartanam · SAIL Digital Transformation<br>"
    f"{B['summary']['commodities_modelable']} commodities under full ML "
    f"coverage · {B['summary']['rows_priced']:,} priced PO lines</span>",
    unsafe_allow_html=True)


def goto_commodity(com):
    st.session_state["commodity"] = com
    st.session_state["page"] = "🔍 Commodity Deep-Dive"
    st.rerun()


def commodity_selector(key, modelable_only=True):
    cat = B["catalog"]
    opts = cat[cat["modelable"]]["commodity"].tolist() if modelable_only \
        else cat["commodity"].tolist()
    default = st.session_state.get("commodity", opts[0])
    if default not in opts:
        default = opts[0]
    return st.selectbox("Commodity", opts, index=opts.index(default), key=key)


# ================================================================ COMMAND CENTER
if page == "🏭 Command Center":
    st.title("🏭 Procurement Command Center")
    st.markdown(f"<span class='smallnote'>Every figure below is computed from "
                f"{B['summary']['rows_priced']:,} purchase-order lines "
                f"({B['summary']['span'][0]} → {B['summary']['span'][1]}). "
                f"Nothing is hand-entered.</span>", unsafe_allow_html=True)

    k = dd.kpis(B)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Spend, last 12 months", inr(k["spend_12m_cr"] * 1e7))
    c2.metric("Commodities tracked", f"{k['n_total']:,}",
              f"{k['n_model']} under ML forecast")
    c3.metric("Buy signals live", k["n_buy"], "BUY NOW + BUY/STAGGER",
              delta_color="off")
    c4.metric("Ordering cycles overdue", k["n_overdue"],
              "vs own historical rhythm", delta_color="off")
    c5.metric("Median forecast error", f"{k['med_mape']*100:.1f}%",
              "champion models, walk-forward", delta_color="off")

    vt = get_impact(artifact_stamp())["table"]
    if len(vt):
        h = vt.iloc[0]
        hc = SIGNAL_COLOURS.get(h["signal"], C["hot"])
        st.markdown(
            f"<div class='hero'>📣 <b>Today's headline call:</b> "
            f"<span class='chip' style='background:{hc}22;color:{hc};"
            f"border:1px solid {hc}66'>{h['signal']}</span> &nbsp;"
            f"<b>{h['commodity'][:52]}</b> — forecast "
            f"{pct(h['exp_move_3m'])} over 3 months, roughly "
            f"<b style='font-family:IBM Plex Mono,monospace'>"
            f"{inr(h['at_stake'])}</b> riding on this cycle's volume. "
            f"Details in the Impact Tracker.</div>",
            unsafe_allow_html=True)

    st.markdown("### Action board")
    board = get_board(artifact_stamp())

    fc1, fc2 = st.columns([1, 2])
    sig_filter = fc1.multiselect("Signal filter", list(SIGNAL_COLOURS),
                                 default=list(SIGNAL_COLOURS))
    search = fc2.text_input("Search commodity", "",
                            placeholder="e.g. FERRO, LIMESTONE, BRICK …")
    view = board[board["signal"].isin(sig_filter)]
    if search.strip():
        view = view[view["commodity"].str.contains(search.strip().upper())]

    show = view[["commodity", "signal", "score", "trend", "move_3m",
                 "last_price", "months_since", "cycle_m", "spend_cr"]].copy()
    ev = st.dataframe(
        show, hide_index=True, height=520, on_select="rerun",
        selection_mode="single-row",
        column_config={
            "commodity": st.column_config.TextColumn("Commodity", width="large"),
            "signal": st.column_config.TextColumn("Signal"),
            "score": st.column_config.ProgressColumn(
                "Buy-timing score", min_value=0, max_value=100, format="%.0f"),
            "trend": st.column_config.LineChartColumn(
                "24-mo price trend", width="medium"),
            "move_3m": st.column_config.NumberColumn(
                "Fcst Δ 3m", format="percent"),
            "last_price": st.column_config.NumberColumn(
                "Last price (₹/unit)", format="localized"),
            "months_since": st.column_config.NumberColumn(
                "Months since PO", format="%.1f"),
            "cycle_m": st.column_config.NumberColumn(
                "Typical cycle (m)", format="%.1f"),
            "spend_cr": st.column_config.NumberColumn(
                "Spend (₹ Cr)", format="%.1f"),
        })
    if ev.selection.rows:
        goto_commodity(view.iloc[ev.selection.rows[0]]["commodity"])
    st.markdown("<span class='smallnote'>Click any row to open its deep-dive. "
                "Signals come from the fuzzy decision engine: forecast "
                "direction × ordering urgency × momentum × volatility.</span>",
                unsafe_allow_html=True)

# ============================================================ COMMODITY DEEP-DIVE
elif page == "🔍 Commodity Deep-Dive":
    st.title("🔍 Commodity Deep-Dive")
    all_toggle = st.toggle("Include long-tail commodities (no ML forecast)",
                           value=False)
    com = commodity_selector("dd_sel", modelable_only=not all_toggle)
    st.session_state["commodity"] = com
    P = dd.commodity_pack(B, com)
    obs, fc, sig, cat = P["obs"], P["forecast"], P["signal"], P["cat"]

    if sig:
        left, right = st.columns([1.25, 1])
        with left:
            colr = sig["colour"]
            st.markdown(
                f"<div class='verdict'>"
                f"<span class='chip' style='background:{colr}22;color:{colr};"
                f"border:1px solid {colr}66'>{sig['label']}</span>"
                f"<div class='lbl' style='color:{colr}'>{sig['score']:.0f} / 100"
                f"<span style='font-size:1rem;color:{C['mute']}'> buy-timing score</span></div>"
                f"<div class='sub'>Last price {inr(sig['last_price'])}/unit · "
                f"forecast Δ3m {pct(sig['exp_move_3m'])} · Δ6m {pct(sig['exp_move_6m'])} · "
                f"Δ12m {pct(sig['exp_move_12m'])}<br>"
                f"{sig['months_since_last']:.1f} months since last PO "
                f"(typical cycle {sig['cycle_months']:.1f} m)</div></div>",
                unsafe_allow_html=True)
            st.markdown("**Why the engine says this**")
            for r in sig["reasons"]:
                st.markdown(f"<div class='reason'>{r}</div>",
                            unsafe_allow_html=True)
            from src.decision_engine import (ai_po_recommendation,
                                             inventory_plan, order_pattern)
            _plan = inventory_plan(P["filled"], cat["last_po"],
                                   cat["median_order_gap_days"],
                                   cat["p90_order_gap_days"],
                                   sig["last_price"], ASOF)
            _pat = order_pattern(P["po"])
            _ai = ai_po_recommendation(_plan, _pat, sig, ASOF)
            ud = f"{_pat['usual_next_date']:%d %b %Y}" \
                if pd.notna(_pat["usual_next_date"]) else "—"
            st.markdown(
                f"<div class='reason' style='border-left-color:{C['blue']}'>"
                f"📦 <b>Order plan:</b> usual habit says {ud} for "
                f"~{_pat['usual_qty']:,.0f}; the engine suggests "
                f"<b>{_ai['date']:%d %b %Y}</b> for ~<b>{_ai['qty']:,.0f}</b>"
                f" (defaults; tune assumptions in the Inventory Planner)."
                f"</div>", unsafe_allow_html=True)
        with right:
            g = go.Figure(go.Indicator(
                mode="gauge+number", value=sig["score"],
                number=dict(font=dict(family="IBM Plex Mono", size=44)),
                gauge=dict(
                    axis=dict(range=[0, 100], tickcolor=C["mute"]),
                    bar=dict(color=sig["colour"], thickness=0.32),
                    bgcolor=C["panel2"], borderwidth=0,
                    steps=[dict(range=[0, 28], color=C["gauge_zones"][0]),
                           dict(range=[28, 42], color=C["gauge_zones"][1]),
                           dict(range=[42, 58], color=C["gauge_zones"][2]),
                           dict(range=[58, 72], color=C["gauge_zones"][3]),
                           dict(range=[72, 100], color=C["gauge_zones"][4])])))
            st.plotly_chart(plotly_base(g, h=300), use_container_width=True)
    else:
        st.info("This commodity sits in the long tail — not enough ordering "
                "history for a defensible ML forecast. Everything below is "
                "descriptive, straight from its PO record.")

    tab_names = ["📈 Forecast 3m", "📈 Forecast 6m", "📈 Forecast 12m",
                 "🗓 Seasonality", "📦 Consumption & ordering", "🧾 PO history",
                 "🧮 Price arithmetic"]
    tabs = st.tabs(tab_names)

    for ti, hor in enumerate((3, 6, 12)):
        with tabs[ti]:
            fig = go.Figure()
            filled = P["filled"]
            fig.add_trace(go.Scatter(
                x=filled["month"], y=filled["price_filled"], mode="lines",
                name="Interpolated grid", line=dict(color=C["line"], width=1.4,
                                                    dash="dot"),
                hovertemplate="%{x|%b %Y}<br>₹%{y:,.0f} (interpolated)<extra></extra>"))
            fig.add_trace(go.Scatter(
                x=obs["month"], y=obs["price"], mode="markers+lines",
                name="Observed PO price", line=dict(color=C["blue"], width=2),
                marker=dict(size=7, color=C["blue"]),
                hovertemplate="%{x|%b %Y}<br>₹%{y:,.0f}<extra>observed</extra>"))
            if len(fc):
                f = fc[fc["horizon"] <= hor]
                fig.add_trace(go.Scatter(
                    x=pd.concat([f["month"], f["month"][::-1]]),
                    y=pd.concat([f["p90"], f["p10"][::-1]]),
                    fill="toself", fillcolor="rgba(255,122,26,0.16)",
                    line=dict(width=0), name="~80% band",
                    hoverinfo="skip"))
                last_obs = obs.iloc[-1]
                fig.add_trace(go.Scatter(
                    x=[last_obs["month"], *f["month"]],
                    y=[last_obs["price"], *f["p50"]],
                    mode="lines+markers", name=f"Forecast ({f['model'].iloc[0]})",
                    line=dict(color=C["hot"], width=3),
                    marker=dict(size=7, symbol="diamond"),
                    hovertemplate="%{x|%b %Y}<br>₹%{y:,.0f}<extra>forecast</extra>"))
            fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.06))
            st.plotly_chart(plotly_base(fig, h=470,
                            title=f"{com} — price history & {hor}-month outlook"),
                            use_container_width=True)
            if len(fc):
                f = fc[fc["horizon"] == hor]
                if len(f):
                    r = f.iloc[0]
                    st.markdown(
                        f"<span class='smallnote'>At month +{hor}: central "
                        f"estimate <b>{inr(r['p50'])}</b>, band "
                        f"{inr(r['p10'])} – {inr(r['p90'])} · champion model: "
                        f"<b>{r['model']}</b>, chosen by walk-forward test on the "
                        f"held-out 20%.</span>", unsafe_allow_html=True)

    with tabs[3]:
        piv = dd.seasonality_matrix(obs)
        if piv.shape[1] >= 2:
            hm = go.Figure(go.Heatmap(
                z=piv.values, x=[str(c) for c in piv.columns], y=list(piv.index),
                colorscale=[[0, C["heat_lo"]], [0.5, C["blue"]], [1, C["hot"]]],
                colorbar=dict(title="₹/unit"),
                hovertemplate="%{y} %{x}<br>₹%{z:,.0f}<extra></extra>"))
            st.plotly_chart(plotly_base(hm, h=430,
                            title="Average purchase price by calendar month"),
                            use_container_width=True)
            st.markdown("<span class='smallnote'>Read across a row: months "
                        "that stay consistently cool are historically cheaper "
                        "windows to buy.</span>", unsafe_allow_html=True)
        else:
            st.info("Not enough distinct years for a seasonality read.")

    with tabs[4]:
        m = P["filled"]
        bar = go.Figure()
        bar.add_trace(go.Bar(x=m["month"], y=m["qty"], name="Qty received",
                             marker_color=C["blue"], opacity=0.85))
        roll = m.set_index("month")["qty"].rolling(6, min_periods=1).mean()
        bar.add_trace(go.Scatter(x=roll.index, y=roll.values, name="6-mo avg",
                                 line=dict(color=C["amber"], width=2.5)))
        st.plotly_chart(plotly_base(bar, h=380,
                        title="Consumption proxy — monthly receipts"),
                        use_container_width=True)
        if cat is not None:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Median order cycle",
                      f"{cat['median_order_gap_days']/30.44:.1f} mo"
                      if np.isfinite(cat['median_order_gap_days']) else "—")
            c2.metric("P90 cycle",
                      f"{cat['p90_order_gap_days']/30.44:.1f} mo"
                      if np.isfinite(cat['p90_order_gap_days']) else "—")
            c3.metric("Avg monthly qty", f"{cat['avg_monthly_qty']:,.0f}")
            c4.metric("Deals under estimate",
                      pct(cat["neg_below_est_share"], signed=False)
                      if np.isfinite(cat["neg_below_est_share"]) else "—")

    with tabs[5]:
        po = P["po"][["PO Date", "PO No", "Quantity Received", "Total PO Value",
                      "resolved_price", "provenance", "Ordering Mode"]].copy()
        po = po.sort_values("PO Date", ascending=False)
        st.dataframe(po, hide_index=True, height=430, column_config={
            "PO Date": st.column_config.DateColumn("PO date", format="DD MMM YYYY"),
            "Quantity Received": st.column_config.NumberColumn(format="localized"),
            "Total PO Value": st.column_config.NumberColumn("PO value (₹)",
                                                            format="localized"),
            "resolved_price": st.column_config.NumberColumn("Unit price (₹)",
                                                            format="localized"),
            "provenance": st.column_config.TextColumn("Price basis"),
        })
        st.markdown("<span class='smallnote'>Price basis: OK = straight from "
                    "PO · RESOLVED_PRQTY / RESOLVED_EST = partial-delivery "
                    "distortion corrected using PR quantity / estimate rate. "
                    "Full audit in Model Lab.</span>", unsafe_allow_html=True)

    with tabs[6]:
        st.markdown("#### Where every number on this page comes from")
        po_a = P["po"].copy()
        RULES_TXT = {
            "OK": "PO value ÷ Qty received (rate consistent with estimate & band)",
            "RESOLVED_PRQTY": "PO value ÷ PR qty — partial delivery, PO qty ≈ PR qty",
            "RESOLVED_EST": "PR est value ÷ PR qty — PO-derived rates implausible",
        }
        mix = po_a["provenance"].value_counts()
        m1, m2, m3 = st.columns(3)
        m1.metric("Straight PO rates", int(mix.get("OK", 0)),
                  "value ÷ qty received", delta_color="off")
        m2.metric("Partial-delivery fixes", int(mix.get("RESOLVED_PRQTY", 0)),
                  "re-priced via PR quantity", delta_color="off")
        m3.metric("Estimate-rate fallbacks", int(mix.get("RESOLVED_EST", 0)),
                  "re-priced via PR estimate", delta_color="off")

        st.markdown("**Step 1 — one trustworthy unit price per PO line**")
        arith = po_a.sort_values("PO Date", ascending=False).head(15)[
            ["PO Date", "Quantity Received", "Total PO Value", "po_unit",
             "PR Qty.", "pr_unit", "alt_unit", "resolved_price", "provenance"]
        ].copy()
        arith["rule applied"] = arith["provenance"].map(RULES_TXT)
        st.dataframe(arith, hide_index=True, height=330, column_config={
            "PO Date": st.column_config.DateColumn(format="DD MMM YYYY"),
            "Quantity Received": st.column_config.NumberColumn(
                "Qty recd", format="localized"),
            "Total PO Value": st.column_config.NumberColumn(
                "PO value ₹", format="localized"),
            "po_unit": st.column_config.NumberColumn(
                "= value ÷ qty", format="localized"),
            "PR Qty.": st.column_config.NumberColumn(
                "PR qty", format="localized"),
            "pr_unit": st.column_config.NumberColumn(
                "PR est rate", format="localized"),
            "alt_unit": st.column_config.NumberColumn(
                "value ÷ PR qty", format="localized"),
            "resolved_price": st.column_config.NumberColumn(
                "→ price used ₹", format="localized"),
        })
        st.markdown("<span class='smallnote'>The cascade per line: accept "
                    "value ÷ qty received when it sits inside this "
                    "commodity's robust band (median ± 3.5 MAD, log scale) "
                    "and agrees with the estimate; else try value ÷ PR qty; "
                    "else the estimate rate; else quarantine. The 'price "
                    "used' column feeds everything downstream.</span>",
                    unsafe_allow_html=True)

        st.markdown("**Step 2 — one price per month (quantity-weighted)**")
        months_opts = list(obs["month"].dt.strftime("%b %Y"))[::-1]
        pick = st.selectbox("Inspect a month", months_opts, index=0,
                            key="arith_month")
        mdt = pd.to_datetime(pick)
        lines = po_a[(po_a["PO Date"].dt.to_period("M").dt.to_timestamp()
                      == mdt)].copy()
        w = lines["Quantity Received"].clip(lower=0).fillna(0)
        lines["weight"] = np.where(w > 0, w, 1.0)
        lines["price × weight"] = lines["resolved_price"] * lines["weight"]
        st.dataframe(lines[["PO Date", "resolved_price", "weight",
                            "price × weight", "provenance"]],
                     hide_index=True, column_config={
            "PO Date": st.column_config.DateColumn(format="DD MMM YYYY"),
            "resolved_price": st.column_config.NumberColumn(
                "price ₹", format="localized"),
            "weight": st.column_config.NumberColumn(format="localized"),
            "price × weight": st.column_config.NumberColumn(
                format="localized")})
        num = float(lines["price × weight"].sum())
        den = float(lines["weight"].sum())
        month_row = obs[obs["month"] == mdt]
        chart_val = float(month_row["price"].iloc[0]) if len(month_row) else np.nan
        st.markdown(
            f"<div class='reason'>Σ(price × weight) ÷ Σ(weight) = "
            f"{num:,.0f} ÷ {den:,.0f} = <b>{(num/den) if den else float('nan'):,.2f}"
            f"</b> — exactly the {pick} point on every chart "
            f"({chart_val:,.2f}).</div>", unsafe_allow_html=True)

        st.markdown("**Step 3 — from history to forecast and band**")
        ch = P.get("champion")
        if ch and len(fc):
            q80 = ch.get("rel_err_q80") or 0.08
            mh = ch.get("mean_h") or 1.0
            f3 = fc[fc["horizon"] == 3]
            ex = f3.iloc[0] if len(f3) else fc.iloc[min(2, len(fc) - 1)]
            band3 = float(abs(ex["p90"] / ex["p50"] - 1))
            st.markdown(
                f"<div class='reason'>Champion <b>{ch['model']}</b> — winner "
                f"of this commodity's walk-forward exam (MAPE "
                f"{ch['mape']*100:.1f}% on {ch['n_test']} held-out months, "
                f"mean horizon {mh:.1f} m) — is refit on the full history "
                f"and pushed 12 months ahead. The band is its own measured "
                f"error: q80 of |relative miss| = {q80*100:.1f}%, widened "
                f"with horizon as q80 × √(h ÷ {mh:.1f}). At h = 3 that gives "
                f"±{band3*100:.1f}%, so p50 {inr(ex['p50'])} → band "
                f"{inr(ex['p10'])} – {inr(ex['p90'])}. Nothing hand-set; "
                f"retrains move all of it.</div>", unsafe_allow_html=True)
        else:
            st.info("No champion forecast for this commodity (long tail).")

# =============================================================== NEGOTIATION ROOM
elif page == "🤝 Negotiation Room":
    st.title("🤝 Negotiation Room")
    st.markdown("<span class='smallnote'>Walk in with numbers, not gut feel. "
                "Bands are built from this commodity's own negotiation record "
                "plus the price forecast.</span>", unsafe_allow_html=True)
    com = commodity_selector("neg_sel")
    P = dd.commodity_pack(B, com)
    obs, sig, cat = P["obs"], P["signal"], P["cat"]
    if not sig:
        st.warning("No forecast coverage for this commodity.")
        st.stop()

    bands = negotiation_bands(
        obs, sig["forecast"],
        sig.get("ratio_q25") or np.nan, sig.get("ratio_q75") or np.nan,
        cat["dominant_mode"])

    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Opening ask", inr(bands["open"]), "start here")
    b2.metric("Target", inr(bands["target"]), "aim to close here")
    b3.metric("Walk-away", inr(bands["walk_away"]), "re-tender above this")
    b4.metric("Buyer leverage",
              f"{bands['power']*100:.0f}/100",
              cat["dominant_mode"].replace("PO MATERIAL - ", "")[:28],
              delta_color="off")

    band_fig = go.Figure()
    hist24 = obs.tail(24)
    band_fig.add_trace(go.Scatter(
        x=hist24["price"], y=[0.5] * len(hist24), mode="markers",
        marker=dict(size=9, color=C["blue"], opacity=0.55),
        name="Last 24 observed prices",
        hovertemplate="₹%{x:,.0f}<extra></extra>"))
    for name, x, colr in (("Open", bands["open"], C["good"]),
                          ("Target", bands["target"], C["amber"]),
                          ("Walk-away", bands["walk_away"], C["bad"])):
        band_fig.add_vline(x=x, line_color=colr, line_width=2.5)
        band_fig.add_annotation(x=x, y=1.02, text=name, showarrow=False,
                                font=dict(color=colr, family="IBM Plex Mono"))
    band_fig.update_yaxes(visible=False, range=[0, 1.15])
    st.plotly_chart(plotly_base(band_fig, h=210,
                    title="Where the bands sit against real history"),
                    use_container_width=True)

    st.markdown("### Assess a vendor quote")
    q1, q2 = st.columns(2)
    quote = q1.number_input("Quoted unit price (₹)", min_value=0.0,
                            value=float(round(bands["target"], 2)), step=1.0,
                            format="%.2f")
    qty = q2.number_input("Quantity under negotiation",
                          min_value=0.0, value=float(
                              max(cat["avg_monthly_qty"] * max(sig["cycle_months"], 1), 1)),
                          step=1.0, format="%.2f")
    cyc = max(int(round(sig["cycle_months"])), 1)
    fc = P["forecast"].set_index("horizon")
    p50_next = float(fc.loc[min(cyc, 12), "p50"]) if len(fc) else bands["target"]
    res = assess_quote(quote, qty, bands, obs["price"].to_numpy(float), p50_next)

    st.markdown(
        f"<div class='verdict'><span class='chip' style='background:{res['colour']}22;"
        f"color:{res['colour']};border:1px solid {res['colour']}66'>"
        f"{res['verdict']}</span>"
        f"<div class='sub' style='margin-top:10px'>"
        f"This quote sits at the <b>{res['percentile']:.0f}th percentile</b> of "
        f"every price ever paid for this material. Suggested counter: "
        f"<b>{inr(res['counter'])}</b>.<br>"
        f"Waiting one full cycle (~{cyc} m) instead of accepting: expected "
        f"{'saving' if res['wait_gain']>0 else 'extra cost'} of "
        f"<b>{inr(abs(res['wait_gain']))}</b> on this quantity "
        f"(forecast {inr(p50_next)}/unit then).</div></div>",
        unsafe_allow_html=True)

    with st.expander("Data-backed talking points"):
        last3 = obs.tail(3)
        best24 = obs.tail(24)["price"].min()
        st.markdown(
            f"- Our last three purchase rates: "
            f"{', '.join(inr(v) for v in last3['price'])} "
            f"({', '.join(m.strftime('%b %y') for m in last3['month'])}).\n"
            f"- Best rate achieved in the last 24 months: **{inr(best24)}**.\n"
            f"- Historically we close **{pct(cat['neg_below_est_share'], signed=False)}"
            f"** of orders below our own estimate on this material.\n"
            f"- Engine outlook: {pct(sig['exp_move_3m'])} over 3 months, "
            f"{pct(sig['exp_move_6m'])} over 6.\n"
            f"- Tender mode leverage: {cat['dominant_mode']}.")

# ============================================================== INVENTORY PLANNER
elif page == "📦 Inventory Planner":
    st.title("📦 Inventory & Ordering Planner")
    st.markdown("<span class='smallnote'>Consumption is proxied by receipts — "
                "the plant's real draw as seen by procurement. Every economic "
                "assumption is a dial, not a hidden constant.</span>",
                unsafe_allow_html=True)
    a1, a2, a3, a4 = st.columns(4)
    lt = a1.slider("Lead time (months)", 0.25, 6.0, 1.0, 0.25)
    sl = a2.select_slider("Service level", [0.90, 0.95, 0.975, 0.99], 0.95)
    oc = a3.number_input("Ordering cost per PO (₹)", 1000.0, 500000.0,
                         25000.0, 1000.0)
    cr = a4.slider("Carrying rate (%/yr of unit value)", 5, 40, 20) / 100

    from src.constraints import (constraints_for, load_constraints,
                                 save_constraints)
    from src.constraints import stamp as constraints_stamp
    from src.decision_engine import (ai_po_recommendation,
                                     build_stagger_plan, order_pattern)

    with st.expander("📋 Ordering constraints — MOQ · max per PO · "
                     "holding capacity (editable)"):
        st.markdown("<span class='smallnote'>Set any that apply; blank = "
                    "unconstrained. These bind every recommendation and "
                    "the staggered plans below. Saved to "
                    "<code>data/constraints.csv</code> — on Streamlit "
                    "Cloud, download and commit it to the repository so "
                    "it survives restarts, exactly like the master "
                    "workbook.</span>", unsafe_allow_html=True)
        _saved = load_constraints()
        _all = B["catalog"][B["catalog"]["modelable"]][["commodity"]].copy()
        _ed = _all.merge(_saved, on="commodity", how="left")
        edited = st.data_editor(
            _ed, hide_index=True, height=280, key="cons_editor",
            column_config={
                "commodity": st.column_config.TextColumn(
                    "Commodity", disabled=True, width="large"),
                "moq": st.column_config.NumberColumn(
                    "MOQ", min_value=0.0, format="localized"),
                "max_oq": st.column_config.NumberColumn(
                    "Max per PO", min_value=0.0, format="localized"),
                "holding_cap": st.column_config.NumberColumn(
                    "Holding capacity", min_value=0.0,
                    format="localized"),
            })
        cc1, cc2 = st.columns([1, 1])
        if cc1.button("💾 Save constraints"):
            issues = save_constraints(edited)
            st.cache_data.clear()
            if issues:
                st.warning("Saved, with issues to fix: "
                           + " · ".join(issues[:4]))
            else:
                st.success("Saved — every plan below now honours them.")
            st.rerun()
        from src.constraints import PATH as _cpath
        if _cpath.exists():
            cc2.download_button(
                "⬇️ Download constraints.csv",
                _cpath.read_bytes(), "constraints.csv", "text/csv",
                help="Commit this to data/ in the repository for "
                     "permanence on Streamlit Cloud.")

    com = commodity_selector("inv_sel")
    P = dd.commodity_pack(B, com)
    cat, sig = P["cat"], P["signal"]
    plan = inventory_plan(P["filled"], cat["last_po"],
                          cat["median_order_gap_days"], cat["p90_order_gap_days"],
                          sig["last_price"] if sig else cat["last_price"],
                          ASOF, lt, sl, oc, cr)
    pattern = order_pattern(P["po"])
    cons = constraints_for(com)
    ai = ai_po_recommendation(plan, pattern, sig, ASOF, cons)

    st.markdown("### Next purchase order — habit vs intelligence")
    u_col, a_col = st.columns(2)
    with u_col:
        ud = f"{pattern['usual_next_date']:%d %b %Y}" \
            if pd.notna(pattern["usual_next_date"]) else "—"
        overdue_tag = " <span style='color:%s;font-weight:600'>(already " \
            "past)</span>" % C["bad"] \
            if pd.notna(pattern["usual_next_date"]) and \
            pattern["usual_next_date"] < ASOF else ""
        st.markdown(
            f"<div class='verdict'><span class='chip' style='background:"
            f"{C['blue']}22;color:{C['blue']};border:1px solid {C['blue']}66'>"
            f"USUAL — historical pattern</span>"
            f"<div class='lbl' style='color:{C['blue']};font-size:1.35rem'>"
            f"{ud}{overdue_tag}</div>"
            f"<div class='sub'>Quantity ≈ <b>{pattern['usual_qty']:,.0f}</b> "
            f"(typical event; middle half "
            f"{pattern['qty_p25']:,.0f}–{pattern['qty_p75']:,.0f})<br>"
            f"Basis: last PO + median gap of "
            f"{pattern['median_gap_days']/30.44:.1f} months, across "
            f"{pattern['n_events']} order events. No models — pure habit."
            f"</div></div>", unsafe_allow_html=True)
    with a_col:
        acolr = SIGNAL_COLOURS.get(ai["label"], C["hot"])
        st.markdown(
            f"<div class='verdict'><span class='chip' style='background:"
            f"{acolr}22;color:{acolr};border:1px solid {acolr}66'>"
            f"AI SUGGESTED — {ai['label']}</span>"
            f"<div class='lbl' style='color:{C['hot']};font-size:1.35rem'>"
            f"{ai['date']:%d %b %Y}</div>"
            f"<div class='sub'>Quantity ≈ <b>{ai['qty']:,.0f}</b><br>"
            f"Basis: price forecast × urgency × the two safety clocks × "
            f"economic order size.</div></div>", unsafe_allow_html=True)
    cons_bits = []
    if np.isfinite(cons["moq"]):
        cons_bits.append(f"MOQ {cons['moq']:,.0f}")
    if np.isfinite(cons["max_oq"]):
        cons_bits.append(f"max/PO {cons['max_oq']:,.0f}")
    if np.isfinite(cons["holding_cap"]):
        cons_bits.append(f"capacity {cons['holding_cap']:,.0f}")
    if cons_bits:
        st.markdown("<span class='smallnote'>Active constraints: "
                    + " · ".join(cons_bits) + "</span>",
                    unsafe_allow_html=True)
    for r in ai["reasons"]:
        st.markdown(f"<div class='reason'>{r}</div>", unsafe_allow_html=True)

    st.markdown("### 🪜 Staggered ordering plan — how much, when, and why")
    stag = build_stagger_plan(plan, pattern, sig, P["forecast"], ASOF,
                              ai["qty"], cons)
    srows, ssum = stag["rows"], stag["summary"]
    if len(srows) <= 1 and ai["label"] not in ("BUY / STAGGER", "WAIT",
                                               "HOLD OFF") \
            and ai.get("n_lots", 1) == 1:
        st.info("One lot satisfies every constraint here — no staggering "
                "needed. The table appears whenever lots must split "
                "(price outlook, per-PO maximum, or holding capacity).")
    if len(srows):
        show = srows.copy()
        st.dataframe(show, hide_index=True, column_config={
            "tranche": st.column_config.NumberColumn("#", width="small"),
            "order_by": st.column_config.DateColumn("Order by",
                                                    format="DD MMM YYYY"),
            "arrives": st.column_config.DateColumn("Arrives (est.)",
                                                   format="DD MMM YYYY"),
            "qty": st.column_config.NumberColumn("Quantity",
                                                 format="localized"),
            "share": st.column_config.NumberColumn("Share",
                                                   format="percent"),
            "price": st.column_config.NumberColumn("Fcst ₹/unit",
                                                   format="localized"),
            "est_cost": st.column_config.NumberColumn("Est. cost ₹",
                                                      format="localized"),
            "cover_after_m": st.column_config.NumberColumn(
                "Cover after (mo)", format="%.1f"),
            "why": st.column_config.TextColumn("Why this tranche",
                                               width="large"),
        })
        mm1, mm2, mm3 = st.columns(3)
        mm1.metric("Staggered plan cost", inr(ssum["est_cost"]),
                   f"{ssum['total_qty']:,.0f} units in {len(srows)} lots",
                   delta_color="off")
        mm2.metric("All-at-once today", inr(ssum["cost_all_now"]),
                   (f"{inr(ssum['vs_all_now'])} saved by staggering"
                    if ssum["vs_all_now"] > 0 else "no timing edge") +
                   ssum.get("cost_all_now_note", ""), delta_color="off")
        mm3.metric("All at the usual date", inr(ssum["cost_all_usual"]),
                   (f"{inr(ssum['vs_all_usual'])} saved vs habit"
                    if ssum["vs_all_usual"] > 0 else "habit comparable"),
                   delta_color="off")
        for w in ssum.get("warnings", []):
            st.warning(w)
        st.markdown("<span class='smallnote'>How it staggers: each "
                    "tranche gets a feasibility window — earliest = when "
                    "holding capacity can absorb it (after the lead "
                    "time), latest = just before stock would run dry — "
                    "and buys at the cheapest champion-forecast price "
                    "inside that window. Monthly granularity; costs use "
                    "forecast p50, so treat them as planning figures, "
                    "not quotes.</span>", unsafe_allow_html=True)

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("EOQ (economic lot)", f"{plan['eoq']:,.0f}"
              if np.isfinite(plan['eoq']) else "—",
              f"≈ {plan['order_cycle_eoq_m']:.1f} mo of demand"
              if np.isfinite(plan['order_cycle_eoq_m']) else "")
    r2.metric("Safety stock", f"{plan['safety_stock']:,.0f}",
              f"{int(sl*100)}% service, LT {lt:g} m", delta_color="off")
    r3.metric("Reorder point", f"{plan['reorder_point']:,.0f}",
              "demand over LT + safety", delta_color="off")
    risk_col = {"LOW": C["good"], "MEDIUM": C["warn"], "HIGH": C["bad"]}[plan["stockout_risk"]]
    r4.metric("Stock-out risk", plan["stockout_risk"],
              f"{plan['months_since_last']:.1f} m since last PO",
              delta_color="off")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Last replenishment", f"{plan['last_event_qty']:,.0f}"
              if np.isfinite(plan.get('last_event_qty', np.nan)) else "—",
              f"≈ {plan['cover_total_m']:.1f} mo of demand"
              if np.isfinite(plan.get('cover_total_m', np.nan)) else "",
              delta_color="off")
    cl = plan.get("cover_left_m", np.nan)
    s2.metric("Est. cover remaining",
              f"{max(cl, 0):.1f} mo" if np.isfinite(cl) else "—",
              "exhausted — running on buffer" if np.isfinite(cl) and cl <= 0
              else "at trailing consumption rate", delta_color="off")
    s3.metric("Expected stock-out",
              f"{plan['stockout_date']:%d %b %Y}"
              if pd.notna(plan.get("stockout_date")) else "—",
              "estimate from receipt flow", delta_color="off")
    s4.metric("Order by (consumption-based)",
              f"{plan['po_by_consumption']:%d %b %Y}"
              if pd.notna(plan.get("po_by_consumption")) else "—",
              f"stock-out minus {lt:g} mo lead time", delta_color="off")

    if pd.notna(plan["next_order_by"]):
        overdue = " — already past; treat as overdue." \
            if plan["next_order_by"] < ASOF else "."
        when = f"<b>{plan['next_order_by']:%d %b %Y}</b>{overdue}"
    else:
        when = "no ordering rhythm established yet."
    st.markdown(
        f"<div class='reason' style='border-left-color:{risk_col}'>"
        f"Two clocks, side by side: the <b>ordering-rhythm clock</b> "
        f"(history says the next PO is typically placed by {when}) and the "
        f"<b>consumption clock</b> above. When they disagree, trust the "
        f"earlier date. Demand ≈ {plan['demand_month']:,.0f}/month "
        f"(σ {plan['demand_sd']:,.0f}).</div>", unsafe_allow_html=True)
    st.markdown("<span class='smallnote'>Honesty note: the SAP export "
                "carries no opening-stock ledger, so cover is estimated as "
                "the last replenishment quantity drawn down at the trailing "
                "36-month average consumption (receipts as proxy). It is a "
                "planning estimate, not a bin reading — the assumptions "
                "above are the dials that drive it.</span>",
                unsafe_allow_html=True)

    st.markdown("### Every commodity — usual vs AI-suggested next PO")

    @st.cache_data(show_spinner="Working out order plans for every commodity…")
    def po_reco_table(_stamp: str, _cstamp: str, lt_, sl_, oc_, cr_):
        from src.constraints import constraints_for, load_constraints
        from src.decision_engine import (ai_po_recommendation, inventory_plan,
                                         order_pattern)
        b = get_bundle()
        cdf = load_constraints()
        rows_ = []
        for _, r_ in b["catalog"][b["catalog"]["modelable"]].iterrows():
            com_ = r_["commodity"]
            s_ = b["signals"].get(com_)
            if not s_:
                continue
            mm = b["monthly"][b["monthly"]["commodity"] == com_]
            pl_ = inventory_plan(mm, r_["last_po"],
                                 r_["median_order_gap_days"],
                                 r_["p90_order_gap_days"], s_["last_price"],
                                 b["asof"], lt_, sl_, oc_, cr_)
            pat_ = order_pattern(b["po"][b["po"]["commodity"] == com_])
            c_ = constraints_for(com_, cdf)
            ai_ = ai_po_recommendation(pl_, pat_, s_, b["asof"], c_)
            cbits = [f"MOQ {c_['moq']:,.0f}" if np.isfinite(c_["moq"])
                     else None,
                     f"≤{c_['max_oq']:,.0f}/PO"
                     if np.isfinite(c_["max_oq"]) else None,
                     f"cap {c_['holding_cap']:,.0f}"
                     if np.isfinite(c_["holding_cap"]) else None]
            cbits = " · ".join(x for x in cbits if x) or "—"
            rows_.append(dict(
                commodity=com_, signal=s_["label"],
                usual_date=pattern_date if (pattern_date := pat_["usual_next_date"]) is not None else pd.NaT,
                usual_qty=pat_["usual_qty"],
                ai_date=ai_["date"], ai_qty=ai_["qty"],
                shift_days=(ai_["date"] - pat_["usual_next_date"]).days
                if pd.notna(pat_["usual_next_date"]) else np.nan,
                lots=ai_.get("n_lots", 1), constraints=cbits,
                risk=pl_["stockout_risk"]))
        return pd.DataFrame(rows_).sort_values("ai_date")

    reco = po_reco_table(artifact_stamp(), constraints_stamp(),
                         lt, sl, oc, cr)
    st.dataframe(reco, hide_index=True, height=420, column_config={
        "commodity": st.column_config.TextColumn("Commodity", width="large"),
        "signal": st.column_config.TextColumn("Signal"),
        "usual_date": st.column_config.DateColumn("Usual next PO",
                                                  format="DD MMM YYYY"),
        "usual_qty": st.column_config.NumberColumn("Usual qty",
                                                   format="localized"),
        "ai_date": st.column_config.DateColumn("AI date",
                                               format="DD MMM YYYY"),
        "ai_qty": st.column_config.NumberColumn("AI qty", format="localized"),
        "shift_days": st.column_config.NumberColumn("AI shift (days)",
                                                    format="%d"),
        "lots": st.column_config.NumberColumn("Lots", width="small"),
        "constraints": st.column_config.TextColumn("Constraints"),
        "risk": st.column_config.TextColumn("Stock risk"),
    })
    st.markdown("<span class='smallnote'>AI shift = AI date minus the usual "
                "habit date. Negative = the engine advances the buy (prices "
                "rising or stock thin); positive = it defers (prices "
                "easing, cover permits). Dial changes above re-plan the "
                "whole table.</span>", unsafe_allow_html=True)

    st.markdown("### Order calendar — top-spend commodities")
    rows = []
    for _, r in B["catalog"][B["catalog"]["modelable"]].head(30).iterrows():
        s = B["signals"].get(r["commodity"])
        if not s:
            continue
        pl = inventory_plan(
            B["monthly"][B["monthly"]["commodity"] == r["commodity"]],
            r["last_po"], r["median_order_gap_days"], r["p90_order_gap_days"],
            s["last_price"], ASOF, lt, sl, oc, cr)
        dates = [d for d in (pl["next_order_by"], pl["po_by_consumption"])
                 if pd.notna(d)]
        if dates:
            rows.append(dict(
                commodity=r["commodity"][:40], next=min(dates),
                risk=pl["stockout_risk"], signal=s["label"],
                stockout=pl["stockout_date"] if pd.notna(pl["stockout_date"])
                else pd.NaT))
    cal = pd.DataFrame(rows).sort_values("next")
    cal["so_txt"] = pd.to_datetime(cal["stockout"]).dt.strftime("%d %b %Y")
    cal["so_txt"] = cal["so_txt"].fillna("n/a")
    calfig = go.Figure()
    for risk, colr in (("HIGH", C["bad"]), ("MEDIUM", C["warn"]),
                       ("LOW", C["good"])):
        d = cal[cal["risk"] == risk]
        calfig.add_trace(go.Scatter(
            x=d["next"], y=d["commodity"], mode="markers",
            marker=dict(size=12, color=colr, symbol="diamond"),
            name=f"{risk} risk", customdata=d["so_txt"],
            hovertemplate="%{y}<br>order by %{x|%d %b %Y} · est. stock-out "
                          "%{customdata}<extra></extra>"))
    calfig.add_vline(x=ASOF, line_color=C["hot"], line_dash="dash")
    calfig.add_annotation(x=ASOF, y=1.02, yref="paper", text="today",
                          showarrow=False, font=dict(color=C["hot"]))
    st.plotly_chart(plotly_base(calfig, h=560, title=None),
                    use_container_width=True)

# ================================================================= MARKET PULSE
elif page == "🌐 Market Pulse":
    st.title("🌐 Market Pulse — external indices")
    from src.external_data import connectivity_probe

    c1, c2, c3 = st.columns([2.2, 1.2, 1])
    insecure = c1.toggle(
        "Plant-network mode (skip SSL verification)",
        value=st.session_state.get("ext_insecure", False),
        key="ext_insecure",
        help="Corporate networks often intercept HTTPS, which breaks "
             "certificate checks. This bypasses verification for the "
             "market-data fetch only. Use on the plant intranet; leave "
             "off elsewhere.")
    if c2.button("🔄 Refresh feeds now"):
        from src.external_data import reset_circuit
        reset_circuit()
        get_external.clear()
        st.rerun()
    st.markdown("<span class='smallnote'>Three data routes, each proven "
                "reachable from the plant network — Yahoo Finance (Indian "
                "indices, freight, GSCI), the World Bank Pink Sheet "
                "(global commodities) and Frankfurter/ECB (USD/INR) — "
                "with caching, a circuit breaker for outages, and a hard "
                "time budget so this page always renders within "
                "seconds.</span>", unsafe_allow_html=True)
    run_probe = c3.button("🩺 Test connectivity")

    with st.expander("Advanced network settings"):
        proxy = st.text_input(
            "Corporate proxy URL (optional)",
            value=st.session_state.get("ext_proxy", ""), key="ext_proxy",
            placeholder="http://proxy.dsp.sail.in:8080",
            help="Most plant networks route internet through a proxy. "
                 "Ask IT for the address; HTTPS_PROXY environment "
                 "variables are also honoured automatically.")

    if run_probe:
        with st.spinner("Probing all four data routes…"):
            probes = connectivity_probe(insecure=insecure,
                                        proxy=proxy or None)
        good = [p for p in probes if p["ok"]]
        if good:
            st.success(f"{len(good)} of {len(probes)} routes reachable — "
                       "the page can serve data on this network.")
        else:
            st.error("All three routes failed. This host has no usable "
                     "outbound internet on 443 — set the proxy above (ask "
                     "IT for the address), or rely on Streamlit Cloud "
                     "where all routes work.")
        for p in probes:
            icon = "🟢" if p["ok"] else "🔴"
            detail = (f"{p['points']} points in {p['seconds']}s"
                      if p["ok"] else f"{p['error']} ({p['seconds']}s)")
            st.markdown(f"{icon} **{p['route']}** — `{detail}`")

    ext, status = get_external(insecure, proxy)
    live = [k for k, v in status.items() if v.startswith("live")]
    cached = [k for k, v in status.items() if v.startswith(("cache", "stale"))]
    down = [k for k, v in status.items()
            if v.startswith(("unavailable", "skipped"))]
    if ext.empty:
        st.error("No external series could be fetched and no cache exists "
                 "yet — the panel will never show invented numbers. Click "
                 "**Test connectivity** above to see the exact blocker; "
                 "the per-series errors are listed below.")
        with st.expander("🔎 Per-series diagnostics", expanded=True):
            for k, v in status.items():
                st.markdown(f"- **{k}** — `{v}`")

        st.markdown("### 🧭 What each benchmark touches in OUR basket "
                    "<span class='smallnote'>(mechanism view — measured "
                    "links appear once feeds load)</span>",
                    unsafe_allow_html=True)

        @st.cache_data(show_spinner=False)
        def get_index_map_offline(_stamp: str):
            from src.external_data import map_indices_to_commodities
            b = get_bundle()
            return map_indices_to_commodities(
                b["catalog"][b["catalog"]["modelable"]])

        _off = get_index_map_offline(artifact_stamp())
        for gtitle, gkey in [("🇮🇳 Indian market signals", "in"),
                             ("🌍 Global cost benchmarks", "global")]:
            st.markdown(f"#### {gtitle}")
            for m in [x for x in _off
                      if x.get("region", "global") == gkey]:
                with st.expander(
                        f"{m['index']}  —  {m['n_matched']} covered "
                        f"commodit{'y' if m['n_matched']==1 else 'ies'}"):
                    st.markdown(f"<div class='reason'>{m['how']}</div>",
                                unsafe_allow_html=True)
                    if m["matched"]:
                        st.markdown(" ".join(
                            f"<span class='chip' style='background:"
                            f"{C['blue']}18;color:{C['blue']};border:1px "
                            f"solid {C['blue']}55;margin:2px'>{c[:38]}"
                            f"</span>"
                            for c in m["matched"][:10]),
                            unsafe_allow_html=True)
    else:
        st.markdown(f"<span class='smallnote'>Sources — live: "
                    f"{len(live)} · cached: {len(cached)} · "
                    f"unavailable/skipped: {len(down)} (exact reasons in "
                    f"diagnostics below). Routes: Yahoo → World Bank → "
                    f"Frankfurter/ECB; cache refreshes every 6 h; outages "
                    f"remembered for 24 h.</span>",
                    unsafe_allow_html=True)
        preferred = ["Nifty Metal (NSE)", "USD / INR",
                     "Iron ore (global, USD/dmt)",
                     "Coal, Australia (USD/mt)",
                     "Global energy price index"]
        default_pick = [c for c in preferred if c in ext.columns]
        for c in ext.columns:
            if len(default_pick) >= 5:
                break
            if c not in default_pick:
                default_pick.append(c)
        pick = st.multiselect("Indices", list(ext.columns),
                              default=default_pick)
        if pick:
            norm = st.toggle("Rebase to 100 at window start", value=True)
            fig = go.Figure()
            for col in pick:
                s = ext[col].dropna().tail(120)
                y = 100 * s / s.iloc[0] if norm and len(s) else s
                fig.add_trace(go.Scatter(x=s.index, y=y, name=col,
                                         mode="lines", line=dict(width=2)))
            st.plotly_chart(plotly_base(fig, h=430,
                            title="Global benchmarks (monthly)"),
                            use_container_width=True)

        st.markdown("### 🧭 What each benchmark touches in OUR basket")
        st.markdown("<span class='smallnote'>Two layers per benchmark: the "
                    "mechanism (why it transmits into the plant's costs) "
                    "and, where live index data overlaps our history, the "
                    "measured monthly correlation at its best lead. "
                    "Mechanism never needs connectivity; measurement is "
                    "labelled returns/levels with its sample size.</span>",
                    unsafe_allow_html=True)

        @st.cache_data(show_spinner=False)
        def get_index_map(_stamp: str, have_cols: tuple):
            from src.external_data import map_indices_to_commodities
            b = get_bundle()
            return map_indices_to_commodities(
                b["catalog"][b["catalog"]["modelable"]],
                ext if len(have_cols) else None,
                b["monthly"] if len(have_cols) else None)

        imap = get_index_map(artifact_stamp(),
                             tuple(sorted(ext.columns)) if not ext.empty
                             else tuple())
        groups = [("🇮🇳 Indian market signals", "in",
                   "Demand-side and domestic cost sentiment — Nifty Metal "
                   "is the closest single dial to this plant's world."),
                  ("🌍 Global cost benchmarks", "global",
                   "Upstream raw-material and currency drivers.")]
        for gtitle, gkey, gsub in groups:
            st.markdown(f"#### {gtitle}")
            st.markdown(f"<span class='smallnote'>{gsub}</span>",
                        unsafe_allow_html=True)
            for m in [x for x in imap if x.get("region", "global") == gkey]:
                live_tag = "" if (not ext.empty and m["index"] in ext.columns) \
                    else " · feed offline — mechanism view only"
                head = (f"{m['index']}  —  {m['n_matched']} covered "
                        f"commodit{'y' if m['n_matched']==1 else 'ies'}"
                        f"{live_tag}")
                with st.expander(head, expanded=False):
                    st.markdown(f"<div class='reason'>{m['how']}</div>",
                                unsafe_allow_html=True)
                    if m["matched"]:
                        chips = " ".join(
                            f"<span class='chip' style='background:{C['blue']}18;"
                            f"color:{C['blue']};border:1px solid {C['blue']}55;"
                            f"margin:2px'>{c[:38]}</span>"
                            for c in m["matched"][:10])
                        more = (f" <span class='smallnote'>+"
                                f"{m['n_matched']-10} more</span>"
                                if m["n_matched"] > 10 else "")
                        st.markdown(chips + more, unsafe_allow_html=True)
                    else:
                        st.markdown("<span class='smallnote'>No covered "
                                    "commodity matches this benchmark — it "
                                    "serves as market context only.</span>",
                                    unsafe_allow_html=True)
                    if m["measured"]:
                        md = pd.DataFrame(m["measured"])
                        md["link"] = md.apply(
                            lambda r: ("moves with" if r["rho"] > 0 else
                                       "moves against") + (
                                f", ~{r['lag']}m ahead" if r["lag"] else
                                ", same month"), axis=1)
                        st.dataframe(
                            md[["commodity", "rho", "lag", "kind", "n", "link"]],
                            hide_index=True, column_config={
                                "rho": st.column_config.NumberColumn(
                                    "ρ", format="%.2f"),
                                "lag": st.column_config.NumberColumn(
                                    "lead (m)"),
                                "kind": st.column_config.TextColumn("basis"),
                                "n": st.column_config.NumberColumn("months"),
                                "link": st.column_config.TextColumn(
                                    "reading", width="medium"),
                            })
                        st.markdown("<span class='smallnote'>ρ from monthly "
                                    "log co-movement; 'levels' basis is used "
                                    "when purchase months are too sparse for "
                                    "return pairs — treat it as association, "
                                    "not causation. A strong 1–3 month lead "
                                    "makes the benchmark an early-warning dial "
                                    "before tenders.</span>",
                                    unsafe_allow_html=True)

        st.markdown("### Which benchmarks lead our prices?")
        com = commodity_selector("mp_sel")
        P = dd.commodity_pack(B, com)
        corr = correlate(P["obs"], ext)
        if corr.empty:
            st.info("Not enough overlapping months to correlate this "
                    "commodity against the external set.")
        else:
            hm = go.Figure(go.Heatmap(
                z=corr.values, x=list(corr.columns), y=list(corr.index),
                zmin=-1, zmax=1,
                colorscale=[[0, C["blue"]], [0.5, C["panel2"]], [1, C["hot"]]],
                colorbar=dict(title="ρ"),
                hovertemplate="%{y} · %{x}<br>ρ = %{z:.2f}<extra></extra>"))
            st.plotly_chart(plotly_base(hm, h=380,
                            title=f"Return correlation — {com}"),
                            use_container_width=True)
            st.markdown("<span class='smallnote'>lag k = the benchmark's move "
                        "k months *before* our purchase price move. A strong "
                        "lag-1/lag-2 cell means that index is an early-warning "
                        "dial worth watching before tenders.</span>",
                        unsafe_allow_html=True)
        with st.expander("🔎 Per-series diagnostics"):
            for k, v in status.items():
                icon = "🟢" if v.startswith("live") else (
                    "🟡" if "cache" in v else "🔴")
                st.markdown(f"{icon} **{k}** — `{v}`")
            st.markdown("<span class='smallnote'>🟢 fetched live this "
                        "session · 🟡 served from disk cache (age shown) · "
                        "🔴 unavailable, exact error shown. Feeds retry "
                        "automatically every 6 hours or on Refresh.</span>",
                        unsafe_allow_html=True)

# ==================================================================== MODEL LAB
elif page == "🧪 Model Lab":
    st.title("🧪 Model Lab — full transparency")
    champs = pd.read_json(PROC / "champions.jsonl", lines=True)
    champs = champs[champs["model"].notna()]
    c1, c2, c3 = st.columns(3)
    c1.metric("Commodities evaluated", len(champs))
    c2.metric("Median champion MAPE", f"{champs['mape'].median()*100:.1f}%")
    c3.metric("Distinct champion models", champs["model"].nunique())

    freq = champs["model"].value_counts().reset_index()
    freq.columns = ["model", "wins"]
    bar = go.Figure(go.Bar(x=freq["wins"], y=freq["model"], orientation="h",
                           marker_color=C["hot"]))
    st.plotly_chart(plotly_base(bar, h=430,
                    title="Which model wins, and how often — no single "
                          "algorithm rules every commodity"),
                    use_container_width=True)

    st.markdown("### Per-commodity bake-off")
    com = commodity_selector("lab_sel")
    P = dd.commodity_pack(B, com)
    lb = P["leaderboard"].copy()
    lb["MAPE %"] = lb["mape"] * 100
    st.dataframe(
        lb[["model", "kind", "MAPE %", "rmse", "mase", "coverage",
            "n_scored", "mean_h"]].round(3),
        hide_index=True, height=420,
        column_config={
            "MAPE %": st.column_config.ProgressColumn(
                "MAPE %", min_value=0,
                max_value=float(min(lb["MAPE %"].replace(np.inf, np.nan)
                                    .dropna().max() * 1.1, 100) or 100),
                format="%.1f"),
            "coverage": st.column_config.NumberColumn("coverage",
                                                      format="percent"),
        })

    tp = P["test_preds"]
    champ_name = lb.iloc[0]["model"]
    tt = tp[tp["model"] == champ_name].sort_values("month")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tt["month"], y=tt["actual"], name="Actual",
                             mode="markers+lines",
                             line=dict(color=C["blue"], width=2),
                             marker=dict(size=9)))
    fig.add_trace(go.Scatter(x=tt["month"], y=tt["pred"],
                             name=f"Predicted ({champ_name})",
                             mode="markers+lines",
                             line=dict(color=C["hot"], width=2, dash="dash"),
                             marker=dict(size=9, symbol="diamond")))
    st.plotly_chart(plotly_base(fig, h=380,
                    title="Held-out 20% test window — champion, walk-forward"),
                    use_container_width=True)
    st.markdown("<span class='smallnote'>Each predicted point was made using "
                "only information available before that month, across the "
                "true gap to the next real PO — if the plant went four months "
                "between orders, the model was scored on a genuine four-step "
                "forecast.</span>", unsafe_allow_html=True)

    with st.expander("🧯 Data-quality quarantine (what the pipeline caught)"):
        q = B["quarantine"]
        st.markdown(
            f"{(q['provenance']=='DROPPED').sum()} PO lines dropped as "
            f"unpriceable, {(q['provenance']=='RESOLVED_PRQTY').sum()} "
            f"partial deliveries re-priced via PR quantity, "
            f"{(q['provenance']=='RESOLVED_EST').sum()} re-priced via "
            f"estimate rate.")
        st.dataframe(q.sort_values("PO Date", ascending=False).head(400),
                     hide_index=True, height=320)

# ================================================================ IMPACT TRACKER
elif page == "🏆 Impact Tracker":
    st.title("🏆 Impact Tracker — what following the engine is worth")
    st.markdown("<span class='smallnote'>Three lenses, never mixed: a "
                "<b>forecast</b> of money at stake today, a <b>verified "
                "ledger</b> that scores past signals as real prices arrive "
                "with each upload, and <b>held-out proof</b> from months the "
                "models never saw.</span>", unsafe_allow_html=True)

    IMP = get_impact(artifact_stamp())
    vt, hind, matured, ledger = (IMP["table"], IMP["hindsight"],
                                 IMP["matured"], IMP["ledger"])

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Direction hit-rate", f"{hind['hit_rate']*100:.0f}%",
              f"{hind['n_decided']} calls, held-out months", delta_color="off")
    k2.metric("Beat the best naive habit by",
              inr(hind["saved_vs_best_naive"]),
              "same months, same tonnages", delta_color="off")
    k3.metric("Perfect foresight captured",
              f"{hind['foresight_capture']*100:.0f}%",
              "of the theoretical maximum", delta_color="off")
    k4.metric("On the table right now", inr(vt["at_stake"].sum()),
              f"{len(vt)} live calls (forecast)", delta_color="off")
    if len(matured):
        k5.metric("Verified ledger to date",
                  inr(matured["follow_gain"].sum()),
                  f"{len(matured)} matured signals", delta_color="off")
    else:
        k5.metric("Verified ledger", "building…",
                  f"{len(ledger)} signals snapshotted", delta_color="off")

    with st.expander("📐 How every rupee figure is computed — rationale "
                     "& steps", expanded=False):
        st.markdown(f"""
**Lens 1 · On the table now (a forecast).**
Step 1: take each live signal's forecast move over 3 months (champion model).
Step 2: take the volume genuinely at stake this cycle = average monthly
quantity × the commodity's own median ordering cycle.
Step 3: money at stake = |forecast move| × last price × that volume.
Rationale: this is the cost difference between buying at today's price and
at the forecast price for the tonnage the plant will buy anyway. MONITOR
signals are excluded — they make no timing claim.

**Lens 2 · Verified ledger (facts, accumulating).**
Step 1: the day signals are issued they are frozen into an append-only
ledger — price, forecast, label, stake volume.
Step 2: when a later upload brings an actual purchase ~3 months on (2–5
month window, nearest to 3), the signal matures.
Step 3: direction verdict = did the realised move match the forecast sign
(moves within ±{DECISION_BAND_PCT}% count as flat, and flat is never marked
wrong). Rupee verdict = BUY family followed means bought at signal-day
price instead of the matured price; WAIT family followed means deferred to
the matured price. Gain = (difference) × stake volume.
Rationale: the counterfactual is the plant's own later price on its own
volume — no market index, no hypothetical.

**Lens 3 · Held-out proof (facts, from the exam window).**
Step 1: every real purchase month in the untouched 20% test window becomes
a decision: cover that month's actual tonnage by locking at the last known
price, or buying on schedule at the month's actual price.
Step 2: the champion's walk-forward forecast makes the call (±{DECISION_BAND_PCT}%
neutral band = no call, scores nothing).
Step 3: charge the engine the honest cost of its choice, then compare
against always-lock, always-wait, and perfect foresight on identical months
and tonnages.
Rationale: the two "always" habits are what a buyer without a model can do;
beating the better of them is the fair bar, and perfect foresight is the
honest ceiling.""")
        dec = hind["decided"]
        ex = dec[(dec["call"] == "buy early") & dec["correct"]
                 & (dec["qty"] > 0)].sort_values("qty", ascending=False)
        if len(ex):
            e = ex.iloc[0]
            saved = (e["actual_price"] - e["prev_price"]) * e["qty"]
            st.markdown(
                f"<div class='reason'><b>Worked example from the exam "
                f"window</b> — {e['commodity'][:44]}, {e['month']:%b %Y}: "
                f"last known price ₹{e['prev_price']:,.0f}, champion "
                f"predicted ₹{e['predicted']:,.0f} → call: <b>buy early</b>. "
                f"Actual price came in at ₹{e['actual_price']:,.0f} on "
                f"{e['qty']:,.0f} units. Following = paid "
                f"₹{e['prev_price']:,.0f}; not following = paid "
                f"₹{e['actual_price']:,.0f}. Benefit of following = "
                f"(₹{e['actual_price']:,.0f} − ₹{e['prev_price']:,.0f}) × "
                f"{e['qty']:,.0f} = <b>{inr(saved)}</b>. Every figure on "
                f"this page is this arithmetic, summed.</div>",
                unsafe_allow_html=True)

    t1, t2, t3 = st.tabs(["💰 On the table now", "✅ Verified track record",
                          "🔬 Held-out proof"])

    with t1:
        st.markdown(
            f"<div class='hero'>If the 3-month forecasts land, the timing "
            f"calls currently live are worth about "
            f"<b style='font-family:IBM Plex Mono,monospace'>"
            f"{inr(vt['at_stake'].sum())}</b> across "
            f"{len(vt)} commodities — money saved by buying before forecast "
            f"rises and deferring ahead of forecast falls, on each "
            f"commodity's typical cycle volume. This is a forecast, and "
            f"it says so.</div>", unsafe_allow_html=True)
        top = vt.head(12).iloc[::-1]
        fig = go.Figure(go.Bar(
            x=top["at_stake"], y=[c[:34] for c in top["commodity"]],
            orientation="h",
            marker_color=[SIGNAL_COLOURS.get(s, C["mute"]) for s in top["signal"]],
            customdata=np.stack([top["signal"], top["exp_move_3m"] * 100], axis=-1),
            hovertemplate="%{y}<br>%{customdata[0]} · Δ3m %{customdata[1]:+.1f}%"
                          "<br>at stake ₹%{x:,.0f}<extra></extra>"))
        st.plotly_chart(plotly_base(fig, h=430,
                        title="Biggest live calls by money at stake"),
                        use_container_width=True)
        show = vt.copy()
        show["at_stake_cr"] = show["at_stake"] / 1e7
        st.dataframe(show[["commodity", "signal", "score", "exp_move_3m",
                           "stake_qty", "at_stake_cr"]],
                     hide_index=True, height=360, column_config={
            "exp_move_3m": st.column_config.NumberColumn("Fcst Δ 3m", format="percent"),
            "score": st.column_config.ProgressColumn("Score", min_value=0,
                                                     max_value=100, format="%.0f"),
            "stake_qty": st.column_config.NumberColumn("Cycle qty", format="localized"),
            "at_stake_cr": st.column_config.NumberColumn("At stake (₹ Cr)", format="%.2f"),
        })

    with t2:
        if matured.empty:
            st.markdown(
                f"<div class='hero'>The accountability loop is armed. "
                f"<b>{len(ledger)}</b> signals were snapshotted on "
                f"<b>{ledger['asof'].max():%d %b %Y}</b> the moment they were "
                f"issued. When future uploads bring the actual PO prices "
                f"(first verdicts expected around "
                f"<b>{(ledger['asof'].max() + pd.DateOffset(months=3)):%b %Y}"
                f"</b>), each signal is scored automatically: did the "
                f"forecast direction come true, and what did following the "
                f"call save or cost on that commodity's real volume? The "
                f"cumulative curve draws itself, upload by upload — no one "
                f"has to remember to keep score.</div>",
                unsafe_allow_html=True)
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Signals matured", len(matured))
            m2.metric("Direction correct",
                      f"{matured['direction_correct'].mean()*100:.0f}%")
            m3.metric("Net gain from following",
                      inr(matured["follow_gain"].sum()))
            fig = go.Figure(go.Scatter(
                x=matured["matured_month"], y=matured["cumulative_gain"],
                mode="lines+markers", line=dict(color=C["hot"], width=3),
                fill="tozeroy", fillcolor="rgba(212,87,15,0.10)"))
            st.plotly_chart(plotly_base(fig, h=340,
                            title="Cumulative verified impact (₹)"),
                            use_container_width=True)
            show = matured.copy()
            show["gain_cr"] = show["follow_gain"] / 1e7
            st.dataframe(show[["asof", "commodity", "label", "exp_move_3m",
                               "realized_move", "direction_correct",
                               "gain_cr"]], hide_index=True, height=360,
                         column_config={
                "exp_move_3m": st.column_config.NumberColumn("Forecast Δ", format="percent"),
                "realized_move": st.column_config.NumberColumn("Realized Δ", format="percent"),
                "gain_cr": st.column_config.NumberColumn("Follow gain (₹ Cr)", format="%.3f"),
            })
        st.markdown("<span class='smallnote'>Scoring rule per signal: BUY "
                    "family followed = bought at signal-day price instead of "
                    "the price ~3 months later; WAIT family followed = "
                    "deferred to the later price. Stake = the commodity's "
                    "average cycle volume. MONITOR signals are not scored — "
                    "they make no timing claim.</span>",
                    unsafe_allow_html=True)

    with t3:
        st.markdown(
            f"<div class='hero'>Replay of the untouched test window: "
            f"<b>{hind['n_events']}</b> real purchase months across all "
            f"commodities, each turned into a timing decision — lock at the "
            f"last known price, or buy on schedule at the month's actual "
            f"price. The champion's forecast made "
            f"<b>{hind['n_decided']}</b> directional calls and got "
            f"<b>{hind['hit_rate']*100:.1f}%</b> right. Same months, same "
            f"tonnages, no hindsight.</div>", unsafe_allow_html=True)
        strat = pd.DataFrame({
            "strategy": ["Perfect foresight", "Following the engine",
                         "Always wait for schedule", "Always lock early"],
            "cost": [hind["cost_perfect"], hind["cost_follow"],
                     hind["cost_always_wait"], hind["cost_always_early"]]})
        colors = [C["mute"], C["hot"], C["blue"], C["blue"]]
        fig = go.Figure(go.Bar(x=strat["cost"], y=strat["strategy"],
                               orientation="h", marker_color=colors,
                               hovertemplate="%{y}: ₹%{x:,.0f}<extra></extra>"))
        st.plotly_chart(plotly_base(fig, h=300,
                        title="Total procurement cost over the test months, "
                              "by strategy"), use_container_width=True)
        tl = hind["timeline"]
        fig2 = go.Figure(go.Scatter(
            x=tl["month"], y=tl["cumulative"], mode="lines",
            line=dict(color=C["hot"], width=3), fill="tozeroy",
            fillcolor="rgba(212,87,15,0.10)",
            hovertemplate="%{x|%b %Y}<br>₹%{y:,.0f}<extra></extra>"))
        st.plotly_chart(plotly_base(fig2, h=320,
                        title="Cumulative advantage vs the best naive habit"),
                        use_container_width=True)
        dec = hind["decided"]
        per = dec.groupby("commodity").agg(
            calls=("correct", "size"), hit_rate=("correct", "mean")).reset_index()
        adv = hind["events"].groupby("commodity")["_adv"].sum().rename("advantage")
        per = per.merge(adv, on="commodity").sort_values("advantage",
                                                          ascending=False)
        per["advantage_cr"] = per["advantage"] / 1e7
        st.dataframe(per[["commodity", "calls", "hit_rate", "advantage_cr"]],
                     hide_index=True, height=330, column_config={
            "hit_rate": st.column_config.NumberColumn("Hit rate", format="percent"),
            "advantage_cr": st.column_config.NumberColumn(
                "Advantage vs best habit (₹ Cr)", format="%.3f")})
        with st.expander("Exactly how this is scored (fairness rules)"):
            st.markdown(f"""
Each test month is one event. The buyer must cover that month's **actual
purchased tonnage** and can pay either the last known price (lock early) or
the month's actual price (buy on schedule). The champion's walk-forward
forecast makes the call; forecast moves inside ±{DECISION_BAND_PCT}% are
treated as no-call and score nothing.

The engine is charged the honest cost of its choice. It is compared against
the two habits a buyer without a model could follow — always lock, always
wait — and against perfect foresight (the cheaper of the two, known only in
hindsight). All four strategies face identical months and tonnages. Every
prediction was produced strictly from information available before the month
in question; ensemble weights never saw these months either.""")

# ============================================================ FORECAST REGISTRY
elif page == "📚 Forecast Registry":
    st.title("📚 Forecast Registry — how every commodity is predicted")
    st.markdown("<span class='smallnote'>One row per covered commodity: "
                "the champion model that won its walk-forward exam, how "
                "that method works in plain words, its measured accuracy "
                "on months it never saw, and a 0–100 confidence score "
                "whose formula is printed right here — no hidden "
                "grading.</span>", unsafe_allow_html=True)

    from src.dashboard_data import registry_frame
    reg = registry_frame(B)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Commodities covered", len(reg))
    k2.metric("High confidence (≥75)",
              int((reg["confidence"] >= 75).sum()),
              "typically tight, reliable forecasts", delta_color="off")
    k3.metric("Moderate (55–75)",
              int(((reg["confidence"] >= 55)
                   & (reg["confidence"] < 75)).sum()),
              "usable with the band in view", delta_color="off")
    k4.metric("Use with care (<55)",
              int((reg["confidence"] < 55).sum()),
              "volatile or thin history — lean on bands",
              delta_color="off")

    with st.expander("📐 How the confidence score is computed"):
        st.markdown("""
Three honest ingredients, weighted **55 / 30 / 15**, each scaled 0–1:

**Accuracy** — the champion's held-out MAPE against a 30% floor:
`acc = 1 − MAPE ÷ 0.30` (a 6% MAPE scores 0.80; 30%+ scores 0).

**Reliability vs naive** — MASE, full credit at ≤ 0.7 (clearly beats
just repeating the last price), zero at ≥ 1.3:
`rel = (1.3 − MASE) ÷ 0.6`.

**Evidence** — how many real purchase months the exam contained, full
credit at 10+: `evid = test months ÷ 10`.

`confidence = 100 × (0.55·acc + 0.30·rel + 0.15·evid)` — descriptive,
recomputed on every retrain, and deliberately harsh: a commodity can
forecast decently yet score Moderate simply because its exam was short.
Grades: **High ≥ 75 · Moderate 55–75 · Use with care < 55**.""")

    fcol1, fcol2 = st.columns([1.4, 2.6])
    gsel = fcol1.multiselect("Filter by grade",
                             ["High", "Moderate", "Use with care"],
                             default=[])
    q = fcol2.text_input("Search commodity", "")
    show = reg.copy()
    if gsel:
        show = show[show["grade"].astype(str).isin(gsel)]
    if q.strip():
        show = show[show["commodity"].str.contains(q.strip().upper(),
                                                   na=False)]
    st.dataframe(show, hide_index=True, height=460, column_config={
        "commodity": st.column_config.TextColumn("Commodity",
                                                 width="large"),
        "spend_cr": st.column_config.NumberColumn("Spend (₹ Cr)",
                                                  format="%.2f"),
        "model": st.column_config.TextColumn("Champion model"),
        "method": st.column_config.TextColumn("How it forecasts",
                                              width="large"),
        "mape": st.column_config.NumberColumn("MAPE", format="percent"),
        "rmse": st.column_config.NumberColumn("RMSE ₹",
                                              format="localized"),
        "mase": st.column_config.NumberColumn("MASE", format="%.2f"),
        "n_test": st.column_config.NumberColumn("Test months"),
        "confidence": st.column_config.ProgressColumn(
            "Confidence", min_value=0, max_value=100, format="%.0f"),
        "grade": st.column_config.TextColumn("Grade"),
    })

    fig = go.Figure(go.Histogram(
        x=reg["confidence"], nbinsx=20, marker_color=C["hot"],
        opacity=0.85,
        hovertemplate="confidence %{x}<br>%{y} commodities<extra></extra>"))
    fig.add_vline(x=75, line_dash="dot", line_color=C["good"])
    fig.add_vline(x=55, line_dash="dot", line_color=C["warn"])
    st.plotly_chart(plotly_base(fig, h=280,
                    title="Confidence distribution across the portfolio"),
                    use_container_width=True)
    st.markdown("<span class='smallnote'>Reading the spread honestly: "
                "high scores cluster on liquid, regularly bought "
                "materials; low scores flag thin or volatile histories "
                "where the uncertainty band — not the point forecast — "
                "is the number to negotiate with. Full per-model exam "
                "scores live in the Model Lab; the same scorecard is "
                "Appendix A of the documents.</span>",
                unsafe_allow_html=True)

# ================================================================ HOW IT WORKS
elif page == "💡 How It Works":
    st.title("💡 How it works, how accurate it is, and why it's different")
    IMP = get_impact(artifact_stamp())
    hind = IMP["hindsight"]
    champs = pd.read_json(PROC / "champions.jsonl", lines=True)
    k = dd.kpis(B)

    st.markdown(
        f"<div class='hero'>This engine reads the plant's own purchasing "
        f"history — {B['summary']['rows_priced']:,} priced PO lines across "
        f"{B['summary']['commodities_total']:,} materials since "
        f"{B['summary']['span'][0][:4]} — and turns it into three things a "
        f"negotiator can act on: <b>when to buy</b>, <b>what to pay</b>, and "
        f"<b>how much to order</b>. No black box: every verdict shows its "
        f"reasons, every forecast shows its test score, every cleaned price "
        f"shows its provenance.</div>", unsafe_allow_html=True)

    st.markdown("### The journey from SAP row to verdict")
    j1, j2, j3, j4, j5 = st.columns(5)
    for col, (t, d) in zip((j1, j2, j3, j4, j5), [
        ("1 · Clean", "Every PO line gets a trustworthy unit price; "
         "partial-delivery distortions are corrected with visible flags."),
        ("2 · Compete", "19 forecasting models + 4 ensembles fight it out "
         "on each commodity's history."),
        ("3 · Referee", "Chronological walk-forward on the final 20% of "
         "observed months — no peeking, ever."),
        ("4 · Crown", "Whatever honestly wins becomes that commodity's "
         "champion and makes its forecasts."),
        ("5 · Decide", "A fuzzy-logic layer fuses forecast, momentum, "
         "urgency and volatility into a plain-English verdict."),
    ]):
        col.markdown(f"<div class='reason' style='min-height:132px'>"
                     f"<b>{t}</b><br><span class='smallnote'>{d}</span></div>",
                     unsafe_allow_html=True)

    st.markdown("### How accurate is it — live numbers, not claims")
    a1, a2, a3, a4, a5 = st.columns(5)
    a1.metric("Median forecast error", f"{champs['mape'].median()*100:.1f}%",
              "MAPE on held-out months", delta_color="off")
    a2.metric("Best quartile", f"{champs['mape'].quantile(.25)*100:.1f}%",
              f"toughest quartile {champs['mape'].quantile(.75)*100:.1f}%",
              delta_color="off")
    a3.metric("Direction hit-rate", f"{hind['hit_rate']*100:.0f}%",
              f"{hind['n_decided']} held-out calls", delta_color="off")
    a4.metric("Foresight captured", f"{hind['foresight_capture']*100:.0f}%",
              "vs perfect timing", delta_color="off")
    a5.metric("Distinct champions", champs["model"].nunique(),
              f"across {len(champs)} commodities", delta_color="off")
    st.markdown(
        f"<span class='smallnote'>Read these the honest way: a 7% median "
        f"error means the typical 1–4 month-ahead price call lands within a "
        f"few percent of the eventual PO rate; some volatile items are "
        f"harder and their pages say so. Every number above recomputes "
        f"whenever new data is uploaded — the Model Lab shows the full "
        f"leaderboard behind them.</span>", unsafe_allow_html=True)

    st.markdown("### What makes it different")
    rows = [
        ("No single winner, on purpose",
         f"Every commodity holds its own championship. Right now "
         f"{champs['model'].value_counts().index[0]} leads with "
         f"{champs['model'].value_counts().iloc[0]} titles, plain baselines "
         f"hold {int(champs['model'].isin(['Naive (last price)', 'Seasonal naive (12m)', 'Drift']).sum())}, "
         f"and ensembles {int(champs['model'].str.startswith('Ensemble').sum())} — "
         f"whatever tests best, rules."),
        ("A referee that can't be fooled",
         "Gap months are interpolated only from the past at every step, "
         "ensemble weights never touch the test window, and accuracy is "
         "scored solely on months with real purchases."),
        ("Cleaning you can audit",
         f"{B['summary']['resolved_prqty'] + B['summary']['resolved_est']:,} "
         f"partial-delivery distortions corrected with provenance flags, "
         f"{B['summary']['rows_dropped']:,} unpriceable lines quarantined — "
         f"inspect every one in the Model Lab."),
        ("Explanations, not oracles",
         "The fuzzy decision layer states its fired rules in plain English; "
         "negotiation bands trace to your own PO-vs-estimate record; every "
         "inventory number exposes its assumptions as dials."),
        ("It keeps score on itself",
         "Every signal is snapshotted the day it's issued. As uploads bring "
         "actual prices, the Impact Tracker verifies each call and grows a "
         "cumulative rupee ledger nobody has to maintain."),
        ("Self-learning without ceremony",
         "Drag in a new SAP export: it merges safely, re-referees only what "
         "changed, and logs the event to an audit trail. Champions rotate "
         "the moment the data says they should."),
    ]
    for i in range(0, 6, 3):
        cols = st.columns(3)
        for col, (t, d) in zip(cols, rows[i:i + 3]):
            col.markdown(f"<div class='reason' style='min-height:150px'>"
                         f"<b>{t}</b><br><span class='smallnote'>{d}</span>"
                         f"</div>", unsafe_allow_html=True)

    st.markdown("### The full methodology, for the curious")
    with st.expander("Price resolution & series construction"):
        st.markdown("""
A unit price is derived for every PO line as value ÷ quantity received.
Because recent POs often show partial receipts against the full order value,
each derived price is cross-checked against the PR estimate rate and the
commodity's own robust price band (median ± 3.5 MAD in log space). Distorted
lines are re-priced using PR quantity or estimate rate — each carries a
visible provenance flag — and unpriceable lines go to a quarantine file.
Prices then aggregate to quantity-weighted monthly figures; gap months are
log-linear interpolated *only from the past* at evaluation time, and model
accuracy is scored exclusively against months containing a real purchase.""")
    with st.expander("The model zoo & the championship"):
        st.markdown(f"""
Every viable commodity ({B['summary']['commodities_modelable']} with ≥20
priced POs across ≥12 months) faces 19 forecasters — naive and
seasonal-naive baselines, drift, moving average, simple/Holt/Holt-Winters
exponential smoothing, the Theta method, linear trend, ridge autoregression,
and ML models (random forest, extra trees, two gradient-boosting variants,
SVR, k-NN, a small neural network, Bayesian ridge, Gaussian process) on
lag/seasonality features — plus four ensembles: top-5 mean, inverse-error
weights, simulated-annealing-optimised weights, and greedy forward
selection. First ~80% of observed months train; the final ~20% is a
walk-forward test where each step forecasts across the true gap to the next
real PO. The champion is whatever wins that test.""")
    with st.expander("Uncertainty bands"):
        st.markdown("""
Forecast bands are empirical: the champion's own held-out error
distribution, widened with horizon (√h). Roughly 80% coverage — because
that is what the backtest measured, not what a formula promises.""")
    with st.expander("The decision layer: fuzzy verdicts, negotiation, inventory"):
        st.markdown("""
A Mamdani fuzzy-inference system (12 rules, trapezoidal memberships,
centroid defuzzification, implemented from first principles) fuses expected
price move, recent momentum, ordering urgency and volatility into the 0–100
buy-timing score; the fired rules are shown as plain-English reasons.
Negotiation bands come from quartiles of PO-price ÷ PR-estimate, the recent
weighted price, the forecast, and a bargaining-power weight by tender mode —
the counter-offer rule is a game-theory-informed heuristic and is labelled
as one. Inventory uses classical EOQ, safety stock and reorder mathematics
with lead time, service level, ordering cost and carrying rate exposed as
dials (the data holds no delivery lead times, so lead time is an explicit
assumption).""")
    with st.expander("External indices & honest limits"):
        st.markdown("""
External signals are fetched live over three routes proven reachable
from the plant network — Yahoo Finance (Indian indices, freight, GSCI),
the World Bank Pink Sheet (global commodities) and Frankfurter/ECB
(USD/INR) — cached to disk and labelled with source and age; when a
route fails, the panel states the exact error rather than inventing a
number. And the honest limits: PO prices are
contract events, not daily spot quotes — between orders the true market is
unobserved. Forecasts assume continuity of specification, tendering practice
and supplier base. Long-tail materials get descriptive analytics, not
forecasts, because pretending otherwise would be fiction. The engine is a
data-backed second opinion that never gets tired; final judgement stays
with the buyer.""")

# ======================================================================= ADMIN
elif page == "⚙️ Admin — Data & Retraining":
    from src.ingest import (already_applied, append_audit, archive_upload,
                            fingerprint, invalidate_models, merge_master,
                            read_audit, validate_workbook)
    from src.train_all import incremental_update

    st.title("⚙️ Data & Retraining")
    st.markdown(
        "Drop the latest SAP export below — same MAIN SHEET layout — and the "
        "portal takes care of the rest: it validates the file, merges it into "
        "the master (new PO lines added, revised lines updated, history never "
        "erased), rebuilds prices, re-referees only the affected commodities, "
        "and writes an audit entry. Uploading the same file twice changes "
        "nothing.")

    st.session_state.setdefault("ingest_done", {})

    u1, u2 = st.columns(2)
    uploaded_by = u1.text_input("Uploaded by", placeholder="Name / employee no.")
    remarks = u2.text_input("Remarks (optional)",
                            placeholder="e.g. monthly refresh, July POs")
    up = st.file_uploader("Drag & drop the PO workbook here (.xlsx)",
                          type=["xlsx"], accept_multiple_files=False)

    if up is not None:
        data = up.getvalue()
        sha = fingerprint(data)

        if sha in st.session_state["ingest_done"]:
            r = st.session_state["ingest_done"][sha]
            st.success(f"**{up.name}** was applied in this session — "
                       f"{r['rows_added']} lines added, {r['rows_updated']} "
                       f"updated, {r['models_retrained']} models refreshed.")
        else:
            prev = already_applied(sha)
            if prev:
                st.info(f"This exact file (SHA {sha[:12]}…) was already "
                        f"applied on **{pd.Timestamp(prev['timestamp']):%d %b %Y, %H:%M}** "
                        f"by **{prev.get('uploaded_by') or 'unrecorded'}** — "
                        f"nothing to do. The merge is idempotent by design.")
            else:
                v = validate_workbook(io.BytesIO(data))
                for msg in v["issues"]:
                    st.warning(msg)
                if not v["ok"]:
                    st.error("Upload **rejected** — the file does not match "
                             "the expected SAP layout. Nothing was changed.")
                    append_audit(dict(
                        timestamp=str(pd.Timestamp.now()), action="REJECTED",
                        filename=up.name, sha256=sha,
                        size_bytes=len(data), uploaded_by=uploaded_by,
                        remarks=remarks, issues=v["issues"]))
                else:
                    st.markdown(f"<span class='smallnote'>Validated: "
                                f"{v['n_rows']:,} usable rows, "
                                f"{v['span'][0]:%b %Y} → {v['span'][1]:%b %Y}. "
                                f"Applying…</span>", unsafe_allow_html=True)
                    t_start = pd.Timestamp.now()
                    with st.status("Updating the portal with the new data…",
                                   expanded=True) as status:
                        st.write("**1/5** Archiving the upload and backing up "
                                 "the current master…")
                        arch = archive_upload(data, up.name, sha)

                        st.write("**2/5** Merging into the master workbook…")
                        stats = merge_master(v["df"])
                        st.write(f"→ {stats['rows_added']:,} lines added · "
                                 f"{stats['rows_updated']:,} updated · "
                                 f"{stats['rows_unchanged']:,} unchanged · "
                                 f"{stats['rows_history_kept']:,} historical "
                                 f"lines untouched")

                        if not stats["write_applied"]:
                            status.update(label="No new information in this "
                                          "file — master unchanged.",
                                          state="complete")
                            append_audit(dict(
                                timestamp=str(t_start), action="NO_CHANGE",
                                filename=up.name, sha256=sha,
                                size_bytes=len(data), uploaded_by=uploaded_by,
                                remarks=remarks, **{k: stats[k] for k in
                                ("rows_in_upload", "rows_unchanged")}))
                            st.session_state["ingest_done"][sha] = dict(
                                rows_added=0, rows_updated=0, models_retrained=0)
                        else:
                            st.write("**3/5** Rebuilding prices, catalog and "
                                     "quarantine audit…")
                            run_pipeline(verbose=False)

                            changed = stats["changed_commodities"]
                            inv = invalidate_models(changed, PROC)
                            st.write(f"**4/5** Re-refereeing affected "
                                     f"commodities ({inv['champions_dropped']}"
                                     f" invalidated + any newly eligible)…")
                            pbar = st.progress(0.0, text="starting…")

                            def cb(i, n, com):
                                pbar.progress((i + 1) / max(n, 1),
                                              text=f"{i+1}/{n} · {com[:46]}")
                            res = incremental_update(progress_cb=cb)
                            pbar.progress(1.0, text="model refresh complete")

                            st.write("**5/5** Refreshing decision signals and "
                                     "clearing caches…")
                            st.cache_data.clear()
                            dur = (pd.Timestamp.now() - t_start).total_seconds()
                            status.update(label=f"Portal updated in "
                                          f"{dur/60:.1f} min.", state="complete")

                            rec = dict(
                                timestamp=str(t_start), action="APPLIED",
                                filename=up.name, sha256=sha,
                                size_bytes=len(data),
                                uploaded_by=uploaded_by, remarks=remarks,
                                rows_in_upload=stats["rows_in_upload"],
                                rows_added=stats["rows_added"],
                                rows_updated=stats["rows_updated"],
                                rows_unchanged=stats["rows_unchanged"],
                                master_rows_after=stats["master_rows_after"],
                                span_after=stats["span_after"],
                                commodities_changed=len(changed),
                                models_retrained=res["models_retrained"],
                                duration_s=round(dur, 1),
                                archived_copy=arch)
                            append_audit(rec)
                            st.session_state["ingest_done"][sha] = rec

                            st.balloons()
                            st.success(f"Done. {stats['rows_added']:,} new PO "
                                       f"lines, {stats['rows_updated']:,} "
                                       f"revised, {res['models_retrained']} "
                                       f"commodity models re-selected. Every "
                                       f"page now reflects the new data.")
                            if st.button("🏭 Open Command Center with the "
                                         "fresh data", type="primary"):
                                st.session_state["page"] = PAGES[0]
                                st.rerun()

        st.markdown("<span class='smallnote'>Running on Streamlit Community "
                    "Cloud? The update is live for everyone immediately, but "
                    "the cloud filesystem resets on reboot — for permanence, "
                    "download the refreshed master below and commit it to "
                    "GitHub (the app redeploys automatically).</span>",
                    unsafe_allow_html=True)
        d1, d2 = st.columns(2)
        master_p = ROOT / "data" / "raw" / "DATA_COMMODITY__PRICING.XLSX"
        d1.download_button("⬇ Download refreshed master workbook",
                           master_p.read_bytes(),
                           file_name="DATA_COMMODITY__PRICING.XLSX")
        audit_df_dl = read_audit()
        if len(audit_df_dl):
            d2.download_button("⬇ Download audit trail (CSV)",
                               audit_df_dl.to_csv(index=False),
                               file_name="upload_audit_trail.csv")

    st.markdown("---")
    st.markdown("### 🧾 Upload audit trail")
    audit = read_audit()
    if audit.empty:
        st.markdown("<span class='smallnote'>No uploads recorded yet. Every "
                    "accepted, rejected or no-change upload will appear here "
                    "with who, when, what changed, and the file's SHA-256 "
                    "fingerprint.</span>", unsafe_allow_html=True)
    else:
        show_cols = [c for c in ["timestamp", "action", "filename",
                                 "uploaded_by", "remarks", "rows_added",
                                 "rows_updated", "commodities_changed",
                                 "models_retrained", "duration_s",
                                 "master_rows_after", "sha256"]
                     if c in audit.columns]
        st.dataframe(audit[show_cols], hide_index=True, height=300,
                     column_config={
                         "timestamp": st.column_config.DatetimeColumn(
                             "When", format="DD MMM YYYY · HH:mm"),
                         "sha256": st.column_config.TextColumn(
                             "File fingerprint", width="medium"),
                         "duration_s": st.column_config.NumberColumn(
                             "Took (s)", format="%.0f"),
                     })

    with st.expander("Advanced — full retrain from scratch"):
        st.markdown("Re-referees **every** commodity against the current "
                    "master (~20 min). Only needed if you suspect artifact "
                    "corruption; the upload flow above already retrains "
                    "whatever an upload affects.")
        if st.button("🏭 Full retrain now"):
            from src.train_all import main as train_main
            with st.status("Full retraining — keep this tab open.",
                           expanded=True):
                import contextlib
                import io as _io
                buf = _io.StringIO()
                for p in ["leaderboard.csv", "champions.jsonl",
                          "test_predictions.csv", "forecasts.csv",
                          "decision_signals.json"]:
                    (PROC / p).unlink(missing_ok=True)
                run_pipeline()
                with contextlib.redirect_stdout(buf):
                    train_main()
                st.text(buf.getvalue()[-3000:])
            st.cache_data.clear()
            st.success("Retraining complete. Reloading…")
            st.rerun()
