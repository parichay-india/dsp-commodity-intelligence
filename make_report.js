const fs = require("fs");
const S = JSON.parse(fs.readFileSync("/tmp/explainer_stats.json", "utf8"));
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  LevelFormat, PageBreak, convertInchesToTwip, HeightRule, AlignmentType,
} = require("docx");

const ACCENT = "C0501F", INK = "1A1A1A", MUTE = "5A6470";
const FONT = "Arial", MONO = "Consolas";
const W = (n) => S.model_wins[n] || 0;

// ------------------------------------------------------------------ helpers
const P = (text, o = {}) => new Paragraph({
  spacing: { after: o.after ?? 160 }, alignment: o.align,
  children: [new TextRun({ text, font: FONT, size: o.size ?? 22,
    bold: o.bold, italics: o.italics, color: o.color ?? INK })],
});
const R = (runs, o = {}) => new Paragraph({
  spacing: { after: o.after ?? 160 },
  children: runs.map(r => (typeof r === "string" ? { text: r } : r))
    .map(r => new TextRun({ font: r.mono ? MONO : FONT, size: r.size ?? 22,
      color: r.color ?? INK, ...r })),
});
const H1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1,
  spacing: { before: 380, after: 200 },
  children: [new TextRun({ text: t, font: FONT, size: 30, bold: true, color: ACCENT })] });
const H2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2,
  spacing: { before: 260, after: 140 },
  children: [new TextRun({ text: t, font: FONT, size: 25, bold: true, color: INK })] });
const H3 = t => new Paragraph({ heading: HeadingLevel.HEADING_3,
  spacing: { before: 200, after: 110 },
  children: [new TextRun({ text: t, font: FONT, size: 22, bold: true, color: "3A424C" })] });
const EQ = t => new Paragraph({ alignment: AlignmentType.CENTER,
  spacing: { before: 60, after: 170 },
  children: [new TextRun({ text: t, font: MONO, size: 21, color: "2B2B2B" })] });

const numbering = [
  { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
    style: { paragraph: { indent: { left: 420, hanging: 260 } },
             run: { color: ACCENT } } }] },
];
const UL = items => items.map(it => new Paragraph({
  numbering: { reference: "bul", level: 0 }, spacing: { after: 100 },
  children: (Array.isArray(it) ? it : [it])
    .map(r => (typeof r === "string" ? { text: r } : r))
    .map(r => new TextRun({ font: r.mono ? MONO : FONT, size: r.size ?? 22,
      color: r.color ?? INK, ...r })),
}));

const T = (head, rows, w) => new Table({
  width: { size: w.reduce((a, b) => a + b, 0), type: WidthType.DXA },
  columnWidths: w,
  borders: {
    top: { style: BorderStyle.SINGLE, size: 6, color: "C9C9C9" },
    bottom: { style: BorderStyle.SINGLE, size: 6, color: "C9C9C9" },
    left: { style: BorderStyle.SINGLE, size: 4, color: "E0E0E0" },
    right: { style: BorderStyle.SINGLE, size: 4, color: "E0E0E0" },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: "E9E9E9" },
    insideVertical: { style: BorderStyle.SINGLE, size: 4, color: "E9E9E9" },
  },
  rows: [
    new TableRow({ tableHeader: true, children: head.map((t, i) => new TableCell({
      width: { size: w[i], type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: "EFE6DF" },
      margins: { top: 85, bottom: 85, left: 130, right: 130 },
      children: [new Paragraph({ children: [new TextRun({ text: t,
        font: FONT, size: 20, bold: true, color: INK })] })] })) }),
    ...rows.map(r => new TableRow({ children: r.map((cell, i) => new TableCell({
      width: { size: w[i], type: WidthType.DXA },
      margins: { top: 70, bottom: 70, left: 130, right: 130 },
      children: [new Paragraph({ children:
        (Array.isArray(cell) ? cell : [cell])
          .map(run => (typeof run === "string" ? { text: run } : run))
          .map(run => new TextRun({ font: run.mono ? MONO : FONT,
            size: run.mono ? 18 : 20, color: run.color ?? INK, ...run })) })],
    })) })),
  ],
});

const CALL = lines => new Table({
  width: { size: 9360, type: WidthType.DXA }, columnWidths: [9360],
  borders: {
    top: { style: BorderStyle.SINGLE, size: 4, color: "E0D8CE" },
    bottom: { style: BorderStyle.SINGLE, size: 4, color: "E0D8CE" },
    left: { style: BorderStyle.SINGLE, size: 14, color: ACCENT },
    right: { style: BorderStyle.SINGLE, size: 4, color: "E0D8CE" },
    insideHorizontal: { style: BorderStyle.NONE },
    insideVertical: { style: BorderStyle.NONE },
  },
  rows: [new TableRow({ children: [new TableCell({
    width: { size: 9360, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, fill: "FBF6F1" },
    margins: { top: 140, bottom: 140, left: 220, right: 220 },
    children: lines.map(l => new Paragraph({ spacing: { after: 70 },
      children: (Array.isArray(l) ? l : [l])
        .map(r => (typeof r === "string" ? { text: r } : r))
        .map(r => new TextRun({ font: FONT, size: r.size ?? 22,
          color: r.color ?? INK, ...r })) })),
  })] })],
});

let FIGN = 0;
const FIG = (title, howto) => {
  FIGN += 1;
  return new Table({
    width: { size: 9360, type: WidthType.DXA }, columnWidths: [9360],
    borders: {
      top: { style: BorderStyle.DASHED, size: 10, color: "B8AFA3" },
      bottom: { style: BorderStyle.DASHED, size: 10, color: "B8AFA3" },
      left: { style: BorderStyle.DASHED, size: 10, color: "B8AFA3" },
      right: { style: BorderStyle.DASHED, size: 10, color: "B8AFA3" },
      insideHorizontal: { style: BorderStyle.NONE },
      insideVertical: { style: BorderStyle.NONE },
    },
    rows: [new TableRow({
      height: { value: 2900, rule: HeightRule.ATLEAST },
      children: [new TableCell({
        width: { size: 9360, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill: "FAF8F5" },
        verticalAlign: "center",
        margins: { top: 160, bottom: 160, left: 220, right: 220 },
        children: [
          new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
            children: [new TextRun({ text: `[ Figure ${FIGN} — ${title} ]`,
              font: FONT, size: 24, bold: true, color: MUTE })] }),
          new Paragraph({ alignment: AlignmentType.CENTER,
            children: [new TextRun({ text: howto, font: FONT, size: 19,
              italics: true, color: MUTE })] }),
        ],
      })],
    })],
  });
};

const kids = [];

// ================================================================ cover
kids.push(
  P("SAIL — DURGAPUR STEEL PLANT", { size: 20, color: MUTE, after: 60 }),
  new Paragraph({ spacing: { after: 90 }, children: [new TextRun({
    text: "Intelligent Commodity Price Prediction & Procurement Decision Engine",
    font: FONT, size: 44, bold: true, color: ACCENT })] }),
  P("Full Project Report — from zero to hero", { size: 27, after: 50 }),
  P("Technology, algorithms, data, results, and the application, explained for a reader starting from nothing",
    { size: 21, color: MUTE, after: 50 }),
  P(`Pravartanam · SAIL Digital Transformation Division · data as of ${S.asof}`,
    { size: 20, color: MUTE, after: 300 }),
  new Paragraph({ spacing: { after: 240 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 10, color: ACCENT } },
    children: [new TextRun({ text: " ", size: 2 })] }),
  P("How to read this report", { bold: true, size: 24, after: 90 }),
  P("It is written for a complete newcomer. Nothing is assumed: every algorithm is introduced from its everyday intuition before its mechanics, every formula is explained in words first, and every claim about accuracy or benefit points to how it was measured. Sections 1–7 tell the story; sections 8–15 are the technical zero-to-hero; sections 16–20 cover the application and operations. Dashed boxes mark where diagrams and screenshots go, each with instructions for producing it. All numbers were computed live from the plant's data and regenerate on every retrain.", { after: 200 }),
  P("Contents", { bold: true, size: 24, after: 110 }),
  ...[
    "1. Executive summary", "2. Background and the problem",
    "3. Objectives and scope", "4. The dataset",
    "5. System architecture and technology stack",
    "6. Data engineering — from raw SAP rows to trustworthy prices",
    "7. Forecasting from zero — concepts, protocol and metrics",
    "8. The model zoo — every algorithm, from intuition to configuration",
    "9. Ensembles — blending models, and simulated annealing from zero",
    "10. The championship — evaluation protocol and results",
    "11. Fuzzy logic and the Mamdani engine — from zero to our verdicts",
    "12. Negotiation analytics", "13. Inventory analytics and PO recommendations",
    "14. Measuring the benefit — the impact framework",
    "15. Results at a glance",
    "16. The application, page by page",
    "17. Self-learning: data refresh, incremental retraining, audit",
    "18. Deployment and operations", "19. Honest limitations", "20. Roadmap",
    "21. Glossary",
    "Appendix A — Commodity-by-commodity prediction scorecard",
    "Appendix B — Dataset column dictionary",
    "Appendix C — The full fuzzy rule base",
  ].map(t => new Paragraph({ spacing: { after: 62 }, indent: { left: 240 },
    children: [new TextRun({ text: t, font: FONT, size: 20, color: INK })] })),
  new Paragraph({ children: [new PageBreak()] }),
);

// ================================================================ 1 exec
kids.push(
  H1("1. Executive summary"),
  P(`Durgapur Steel Plant spends roughly ₹${S.spend12_cr.toLocaleString("en-IN")} crore a year buying ferro alloys, refractories, electrodes, spares and consumables whose prices move constantly. The buying decisions — when to purchase, what price is fair, how much to order — were made from habit and instinct because the evidence, ${S.rows_raw.toLocaleString("en-IN")} purchase-order lines spanning ${S.years} years, was unreadable at human scale.`),
  P(`This project turned that record into a decision engine. It cleans every PO line into a trustworthy unit price (correcting ${S.resolved.toLocaleString("en-IN")} partial-delivery distortions with visible flags), runs a fair tournament of 19 forecasting algorithms plus 4 ensembles on each of ${S.modelable} commodities, crowns whatever honestly wins a strictly chronological test, converts forecasts into plain-English buy/wait verdicts through a fuzzy-logic layer, derives negotiation bands from the plant's own record, estimates stock cover and stock-out dates from receipt flow, and measures its own benefit in rupees as reality arrives.`),
  T(["Headline result", "Measured value"], [
    ["Forecast accuracy", `median error ${S.mape_med}% on held-out months (best quartile ${S.mape_q25}%, hardest ${S.mape_q75}%)`],
    ["Direction calls", `${S.hit_rate}% of ${S.n_calls} up/down calls correct on months the models never saw`],
    ["Rupee benefit (replay)", `following the engine beat the best naive habit by ₹${S.saved_vs_best_cr} crore across ${S.n_events} real purchase months; ₹${S.saved_vs_early_cr} crore vs always locking early`],
    ["Foresight captured", `${S.capture}% of the perfect-timing ceiling`],
    ["Live now", `${S.live_calls} open timing calls worth about ₹${S.on_table_cr} crore over the next quarter (a forecast, labelled as one)`],
  ], [2600, 6760]),
  P("Delivery: a nine-page web application (Streamlit), a self-service drag-and-drop data-refresh loop with incremental retraining and an audit trail, an executed model-laboratory notebook, and this documentation set. Everything runs on free infrastructure and regenerates from a single SAP export.", { after: 60 }),
);

// ================================================================ 2 background
kids.push(
  H1("2. Background and the problem"),
  P("A negotiator handling a purchase requisition typically cannot see: the last five prices the plant paid, whether the price is trending, whether waiting a month is likely cheaper, what a defensible counter-offer is, or whether stock will run out first. All of it exists in SAP — spread across thousands of rows nobody can hold in their head for thousands of materials."),
  P("The consequences are quiet but real: purchases timed by requisition date instead of the market, quotes judged against memory, order quantities set by habit, stock-outs discovered instead of predicted, and negotiation knowledge that leaves when a person transfers. The plant pays for timing it never consciously chose."),
  CALL([[{ text: "The project's stance: ", bold: true },
    "do not replace the buyer — arm them. Every output is a recommendation with its reasoning attached, and the final call always stays human."]]),
);

// ================================================================ 3 objectives
kids.push(
  H1("3. Objectives and scope"),
  ...UL([
    [{ text: "Predict", bold: true }, `: commodity-wise price forecasts at 3, 6 and 12 months with honest uncertainty bands, using whichever algorithm demonstrably works best per commodity.`],
    [{ text: "Decide", bold: true }, ": convert forecasts + urgency + volatility into a plain-English buy-timing verdict with visible reasons."],
    [{ text: "Negotiate", bold: true }, ": opening / target / walk-away bands from the plant's own record, quote assessment, counter-offers, cost of waiting."],
    [{ text: "Plan inventory", bold: true }, ": economic order quantities, safety stock, estimated cover, stock-out dates, and a dual next-PO recommendation — the historical habit beside the AI suggestion."],
    [{ text: "Prove it", bold: true }, ": leakage-safe evaluation, a self-verifying impact ledger, and full transparency down to the arithmetic of every number."],
    [{ text: "Sustain it", bold: true }, ": drag-and-drop refresh, incremental retraining, audit trail, free hosting."],
  ]),
  P(`Scope: the ${S.modelable} commodities with enough history for defensible modelling (≥20 priced POs across ≥12 observed months) receive the full treatment; the long tail (${(S.materials - S.modelable).toLocaleString("en-IN")} materials, median ${S.median_pos_per_material} POs each) receives descriptive analytics — honesty over theatre.`),
);

// ================================================================ 4 dataset
kids.push(
  H1("4. The dataset"),
  P(`One input, no manual entry: the SAP purchase-order register. ${S.rows_raw.toLocaleString("en-IN")} lines, ${S.materials.toLocaleString("en-IN")} distinct materials, ${S.span[0]} to ${S.span[1]}, total recorded spend ₹${S.total_spend_cr.toLocaleString("en-IN")} crore. Each line carries the material, dates, quantity received, PO value, the plant's own pre-tender estimate, and the tender mode. The full column dictionary is Appendix B.`),
  FIG("Sample of the raw SAP export",
      "Screenshot the first ~15 rows of MAIN SHEET in Excel (blur nothing — it is internal data) showing all twelve columns."),
  H2("4.1 The quality trap that shaped the whole pipeline"),
  P("Unit price looks trivial — PO value ÷ quantity received — but recent orders often record a partial receipt against the full order value, so the naive division invents a price spike that never happened."),
  CALL([
    [{ text: "The Silico Manganese case. ", bold: true },
     `May 2026 rows appear to show ₹${S.simn_fake} per tonne — two to three times market. Only part of the tonnage had arrived against the full value. The pipeline detects the inconsistency and recovers the genuine contracted rate of ₹${S.simn_true}. Left uncorrected, this artefact would have poisoned the forecasts of the plant's single biggest spend item.`],
    [`Across the register: ${S.resolved.toLocaleString("en-IN")} lines corrected with visible provenance flags, ${S.rows_dropped} indefensible lines quarantined for inspection. Nothing silently altered.`],
  ]),
);

// ================================================================ 5 architecture
kids.push(
  H1("5. System architecture and technology stack"),
  P("The design separates heavy offline computation from a light interactive front end. Training (cleaning, tournament, forecasts, signals) runs as a script and writes artifacts; the dashboard only reads artifacts and runs quick interactive mathematics, so it stays fast on free hosting."),
  FIG("System architecture",
      "Generate with Prompt 3 in prompts.docx (or draw in draw.io/PowerPoint to the same specification): a six-block left-to-right chain — SAP export → data pipeline → bake-off engine (orange) → decision layer (orange) → artifacts store → 10-page Streamlit dashboard — with the external-feeds block (Yahoo Finance · World Bank Pink Sheet · Frankfurter/ECB) feeding Market Pulse, the GitHub → Streamlit Cloud hosting block beneath, and the dashed orange Admin feedback loop back to the pipeline."),
  T(["Layer", "Technology", "Why"], [
    ["Language", [{ text: "Python 3.12", mono: true }], "The standard for data science; one language end to end."],
    ["Data handling", [{ text: "pandas, NumPy, openpyxl", mono: true }], "Reads, cleans and reshapes the Excel register in seconds."],
    ["Machine learning", [{ text: "scikit-learn", mono: true }], "Forests, boosting, SVR, k-NN, neural net, Bayesian ridge, Gaussian process — one consistent API."],
    ["Classical forecasting", "custom code", "Holt-Winters, Theta and family written from first principles so the identical code runs anywhere, including offline."],
    ["Optimisation", [{ text: "SciPy dual_annealing", mono: true }], "Tunes the blended-ensemble weights (section 9)."],
    ["Fuzzy inference", "custom Mamdani engine", "Twelve transparent rules; ~150 lines; no black box (section 11)."],
    ["Front end", [{ text: "Streamlit + Plotly", mono: true }], "Interactive web app straight from Python; hover/zoom charts."],
    ["External data", [{ text: "Yahoo Finance, World Bank Pink Sheet, Frankfurter/ECB", mono: true }], "Key-less market feeds — Indian indices, global commodities, USD/INR — with disk caching, circuit breakers and honest failure states."],
    ["Hosting & versioning", "GitHub + Streamlit Community Cloud", "Free, private, auto-redeploy on every data push."],
  ], [1750, 2650, 4960]),
);

// ================================================================ 6 pipeline
kids.push(
  H1("6. Data engineering — from raw rows to trustworthy prices"),
  H2("6.1 The price-resolution cascade"),
  P("For every PO line the pipeline computes three candidate rates — value ÷ quantity received, value ÷ PR quantity, and the estimate rate (PR value ÷ PR quantity) — and anchors a robust plausibility band on the commodity's own history:"),
  EQ("band = median(log price) ± 3.5 × MAD(log price)"),
  P("MAD is the median absolute deviation — like standard deviation but immune to the very outliers being hunted; working in logarithms makes the band symmetric in percentage terms. The cascade then accepts the first candidate that fits: the straight PO rate when it sits in-band and agrees with the estimate (flag OK); else value ÷ PR quantity, the usual fix when a delivery is partial (flag RESOLVED_PRQTY); else the estimate rate (RESOLVED_EST); else the line is quarantined. Every price used downstream carries its flag, and the Deep-Dive's Price-arithmetic tab shows this table live for any commodity."),
  H2("6.2 One price per month, weighted by tonnage"),
  EQ("monthly price = Σ(priceᵢ × qtyᵢ) ÷ Σ(qtyᵢ)   over that month's PO lines"),
  P("Large purchases count more than token ones — the monthly figure is the price the plant's money actually experienced."),
  H2("6.3 The no-time-travel rule"),
  P("Purchase months are irregular, and models need a regular grid, so gap months are filled by straight-line interpolation in log space — but only ever from past observations at the moment of evaluation, and accuracy is scored exclusively against months containing a real purchase. This single discipline is what makes every accuracy number in this report survive scrutiny."),
  FIG("Data pipeline flow",
      "Generate with Prompt 4 in prompts.docx: the resolution cascade with its decision diamonds, the red quarantine branch and live line counts, into the weighted monthly series and past-only grid."),
);

// ================================================================ 7 forecasting 101
kids.push(
  H1("7. Forecasting from zero — concepts, protocol and metrics"),
  H2("7.1 What a time series is, and what a model may look at"),
  P("A time series is just values in time order — here, one price per month per commodity. A forecasting model is any rule producing tomorrow's value from today's history. The information it may draw on: recent values (lags: the price 1, 2, 3 … 12 months ago), summaries of recent behaviour (rolling means and spreads over 3/6/12 months), calendar position (month-of-year, encoded as a smooth sine/cosine pair so December sits next to January), and the overall passage of time. The machine-learning models in section 8 all consume exactly this feature set."),
  H2("7.2 Why testing needs a time machine (walk-forward)"),
  P("Shuffling data into train and test — normal elsewhere in ML — is cheating with time series, because the model would 'train' on the future. The honest protocol is chronological: the first ~80% of observed months train the model, and the final ~20% form the exam. The exam itself is walk-forward: stand at a point in time, predict the next real purchase month (even if it comes four months later — a genuine multi-step forecast), reveal the truth, step forward, repeat."),
  EQ("|—————— ~80% train ——————|—— ~20% walk-forward test ——|"),
  FIG("Walk-forward evaluation",
      "Generate with Prompt 5 in prompts.docx: irregular purchase-month dots, the shaded exam window, and three 'now' cursors forecasting across true gaps."),
  H2("7.3 The three scores used everywhere"),
  ...UL([
    [{ text: "MAPE — mean absolute percentage error. ", bold: true },
     "Average miss in per cent. Predict ₹100, actual ₹107 → miss 7%. Do that over every exam month and average. Intuitive and scale-free, which is why it ranks the tournament."],
    [{ text: "RMSE — root-mean-square error. ", bold: true },
     "Average miss in rupees, but squared first so one huge blunder hurts more than many tiny ones — a penalty for occasional wildness. Scale depends on the commodity's price level."],
    [{ text: "MASE — mean absolute scaled error. ", bold: true },
     "The model's average miss divided by a naive forecaster's average miss on the same series. Below 1.0 means it beats naive; the honest yardstick when comparing across very different commodities."],
  ]),
  P("Champion selection per commodity: lowest MAPE on the exam, RMSE as tie-break, and a model must have produced forecasts for at least 70% of exam months to qualify. The full per-commodity scorecard with all three metrics is Appendix A."),
);

// ================================================================ 8 model zoo
const algo = (title, wins, intuition, how, config) => [
  H3(`${title}  —  ${wins} championship${wins === 1 ? "" : "s"} here`),
  R([{ text: "Intuition. ", bold: true }, intuition]),
  R([{ text: "How it works. ", bold: true }, how]),
  R([{ text: "Configuration in this project. ", bold: true }, config], { after: 200 }),
];

kids.push(
  H1("8. The model zoo — every algorithm, from intuition to configuration"),
  P(`Nineteen forecasters compete on every commodity. They range from one-line common sense to genuine machine learning — deliberately, because the tournament's most important finding is that no single method rules: ${S.n_champ_models} different algorithms hold championships. Baselines are not filler; they won ${S.baseline_wins} titles outright, and knowing where sophistication does NOT pay is itself intelligence. Each entry below: everyday intuition, then mechanics, then the exact setup here, with its championship count on the plant's data.`),

  H2("8.1 The honest baselines"),
  ...algo("Naive (last price)", W("Naive (last price)"),
    "Tomorrow will look like today. For sticky, contract-anchored prices this is brutally hard to beat.",
    "The forecast for every future month is simply the last observed price. No parameters, no fitting.",
    "Used exactly as stated; also supplies the denominator of MASE for every other model."),
  ...algo("Seasonal naive (12 m)", W("Seasonal naive (12m)"),
    "Next March will look like last March — the play for materials with an annual rhythm (monsoon logistics, budget cycles).",
    "The forecast h months ahead is the value observed 12 months before that point.",
    "Season length fixed at 12; falls back to plain naive when history is shorter than a year."),
  ...algo("Drift", W("Drift"),
    "Draw a line from the first price to the last and extend it.",
    "Forecast = last value + h × average historical step (last − first, divided by the number of steps).",
    "No tuning; a straight-edge sanity check on slow steady trends."),
  ...algo("Moving average (auto-k)", W("Moving average (auto-k)"),
    "Ignore the noise; the truth is the recent average.",
    "Forecast = mean of the last k months, held flat. Small k reacts fast; large k stays calm.",
    "k is chosen from {3, 6, 12} by one-step accuracy on a validation tail inside the training window — the model tunes itself without ever touching the exam. Champion of the plant's biggest item, Silico Manganese, at 5.5% MAPE."),

  H2("8.2 The exponential-smoothing family"),
  P("One idea, three levels of sophistication: recent months matter more than old ones, with importance fading exponentially — this month full weight, last month a fraction α less, and so on."),
  ...algo("Simple exponential smoothing (SES)", W("Simple exp. smoothing"),
    "A weighted average where yesterday counts more than last year.",
    "Maintains one number, the level: level ← α × latest + (1 − α) × previous level. Forecast = current level, held flat. α near 1 = jumpy and responsive; near 0 = smooth and stubborn.",
    "α picked from a grid (0.05–0.9) by validation-tail accuracy."),
  ...algo("Holt's trend (damped, auto)", W("Holt trend (damped-auto)"),
    "SES plus a sense of direction.",
    "Two smoothed states — level and trend — updated together; forecast = level + h × trend. Damping multiplies the trend by φ each step so a recent run-up doesn't extrapolate forever: forecast = level + (φ + φ² + … + φʰ) × trend.",
    "α, β and φ grid-searched on the validation tail; φ = 1 (no damping) allowed to win where trends genuinely persist."),
  ...algo("Holt-Winters seasonal", W("Holt-Winters seasonal"),
    "Level + trend + a repeating seasonal fingerprint.",
    "Adds twelve seasonal offsets, one per calendar month, each smoothed by γ as its month recurs; forecast = level + h × trend + the offset for that future calendar month.",
    "Additive form on log prices (so seasonality is percentage-like); needs ≥ 2 full seasons of history; α/β/γ grid-searched."),

  H2("8.3 Theta — the quiet M3-competition winner"),
  ...algo("Theta method", W("Theta method"),
    "Split a series into its calm long-term line and an exaggerated short-term version; forecast each with the tool that suits it; average.",
    "θ = 0 line: the plain linear trend. θ = 2 line: the data with deviations from that trend doubled (short-term movement amplified) — forecast by SES. Final forecast = the average of the two. This modest recipe won the influential M3 forecasting competition.",
    "Classic Theta(0, 2); the SES α self-tunes on the validation tail."),

  H2("8.4 Regression approaches"),
  ...algo("Linear trend", W("Linear trend"),
    "Fit the single best straight line through the whole history and extend it.",
    "Ordinary least squares of log price against time; forecasting extends the line.",
    `On log prices a straight line is a constant percentage drift — a natural model for steadily inflating materials, which is why this humble method leads the whole championship table with ${W("Linear trend")} titles.`),
  ...algo("Autoregressive with ridge (RidgeAR)", W("Autoregressive (ridge)"),
    "Next month is a weighted mix of the last p months — let regression find the weights, gently restrained.",
    "Linear regression on lags 1…p with an L2 (ridge) penalty that shrinks coefficients toward zero, preventing wild weights on short histories. Multi-step forecasts feed each prediction back in as the next lag (recursive forecasting).",
    "p from {3, 6, 12} and the penalty strength from {0.1, 1, 10}, both validation-tuned."),
  ...algo("Bayesian ridge (lags)", W("Bayesian ridge (lags)"),
    "RidgeAR where the data itself decides how much restraint to apply.",
    "Treats coefficients as uncertain quantities and infers both them and the right amount of shrinkage from the data — no grid search needed, naturally cautious on thin histories.",
    "scikit-learn's BayesianRidge on the shared lag/seasonality feature set; standard-scaled inputs."),

  H2("8.5 Tree-based machine learning"),
  P("Decision trees ask a chain of yes/no questions about the features ('was last month's price above ₹71,000? is it a monsoon month?') and predict the average of the historical cases that answered the same way. Single trees memorise noise; the cures are crowds and sequences:"),
  ...algo("Random forest", W("Random forest"),
    "Ask hundreds of slightly different trees and average their answers.",
    "Each of 120 trees trains on a random resample of history and considers random feature subsets at each split — decorrelated opinions whose average is stable.",
    "120 trees, minimum 2 samples per leaf; recursive multi-step forecasting on the shared feature set."),
  ...algo("Extra trees", W("Extra trees"),
    "A forest that decides its split points partly at random — even more diverse opinions.",
    "Identical crowd idea, but split thresholds are drawn randomly rather than optimised, trading a little individual accuracy for extra decorrelation.",
    "Same size and settings as the forest."),
  ...algo("Gradient boosting", W("Gradient boosting"),
    "Build small trees one after another, each one correcting the errors of the team so far.",
    "Tree k fits the residuals left by trees 1…k−1; predictions add up, each dampened by a small learning rate so no single tree dominates.",
    "150 depth-3 trees, learning rate 0.05, 90% row subsampling for regularisation."),
  ...algo("Hist gradient boosting", W("Hist gradient boosting"),
    "Gradient boosting rebuilt for speed and built-in restraint (the LightGBM idea).",
    "Buckets feature values into histograms before splitting — far faster — and adds L2 regularisation on leaf values.",
    `Up to 180 iterations, depth 3, L2 = 1.0. The strongest pure-ML performer here with ${W("Hist gradient boosting")} championships.`),

  H2("8.6 Other machine-learning perspectives"),
  ...algo("Support vector regression (RBF)", W("Support vector (RBF)"),
    "Fit the flattest curve that stays within a tolerance tube around the data, ignoring points already inside the tube.",
    "Only points outside the ε-tube (the support vectors) shape the fit; the RBF kernel lets that fit bend smoothly and non-linearly.",
    "C = 3 (tube stiffness), ε = 0.01, kernel width auto ('scale'); inputs standard-scaled."),
  ...algo("k-nearest neighbours", W("K-nearest neighbours"),
    "Find the five moments in history that look most like today, and predict what happened next then.",
    "Distance in feature space defines 'looks like'; the forecast is the distance-weighted average of those five precedents' outcomes. No training phase at all — the history is the model.",
    "k = 5, distance weighting, scaled features."),
  ...algo("Neural network (MLP)", W("Neural net (MLP)"),
    "Many tiny adjustable switches between input and output that gradually rewire themselves to reduce error.",
    "One hidden layer of 24 neurons, each computing a weighted sum passed through a bend (activation); training nudges every weight downhill on the error surface (back-propagation). Early stopping halts training the moment validation error stops improving — the standard guard against memorising noise.",
    "Hidden layer (24), L2 α = 0.001, max 400 epochs, early stopping; deliberately small because monthly histories are short."),
  ...algo("Gaussian process", W("Gaussian process"),
    "Instead of one best curve, keep every smooth curve consistent with the data, weighted by plausibility — the forecast is their average.",
    "A kernel encodes 'nearby months have similar prices'; prediction is exact probabilistic inference over curves. Exquisite on small data, but the cost grows with the cube of the number of points.",
    "RBF + white-noise kernel, trained on a capped window of the most recent 84 months to keep the cubic cost sane."),
);

// ================================================================ 9 ensembles
kids.push(
  H1("9. Ensembles — blending models, and simulated annealing from zero"),
  P("Different models make different mistakes; averaging uncorrelated mistakes cancels part of them. Four blending strategies enter the tournament as competitors in their own right — and win only where the blend genuinely beats every individual on held-out months. Crucially, blend weights are learned on an inner validation slice inside the training window, never on the exam."),
  ...UL([
    [{ text: `Top-5 mean (${W("Ensemble: top-5 mean")} title). `, bold: true },
     "Equal-weight average of the five best inner-validation models. Simple, robust — and the champion of graphite electrodes at 1.3% MAPE."],
    [{ text: `Inverse-error weights (${W("Ensemble: inverse-error")} title). `, bold: true },
     "Each of the top eight models gets weight proportional to 1 ÷ its validation error — better models speak louder, none is silenced."],
    [{ text: `Annealed weights (${W("Ensemble: annealed weights")} title). `, bold: true },
     "Weights optimised directly against validation MAPE by simulated annealing — explained below."],
    [{ text: `Greedy forward selection (${W("Ensemble: greedy selection")} title). `, bold: true },
     "Start empty; repeatedly add whichever model (repeats allowed) most improves the blend; stop when nothing helps. Caruana's classic recipe — repeats act as implicit weights."],
  ]),
  H2("9.1 Simulated annealing, from zero"),
  P("Finding the best weights is an optimisation problem: imagine a hilly landscape where every location is a possible weight combination and altitude is the validation error — we want the lowest valley. A naive 'always walk downhill' search gets trapped in the first small dip it finds (a local minimum)."),
  P("The fix borrows from metallurgy — fitting, for a steel plant. Annealing cools hot metal slowly so its atoms escape strained arrangements and settle into a strong crystal. Simulated annealing searches the same way: early on, at high 'temperature', the search sometimes accepts uphill moves (worse solutions), letting it jump out of small dips; as the temperature is lowered on a schedule, uphill moves become rarer, and the search settles into a deep valley. Given a slow enough schedule it provably finds the global best."),
  P("Here, SciPy's dual_annealing (a modern generalised variant) searches the weight space through a softmax parametrisation — an elegant trick guaranteeing every candidate is a valid set of positive weights summing to one — for at most 60 iterations per commodity, minimising inner-validation MAPE over the top eight models."),
  CALL([[{ text: "Honesty note: ", bold: true },
    `sophistication buys nothing by right. Across ${S.modelable} commodities the four ensembles together won ${S.ensemble_wins} championships — exactly the ones where blending demonstrably beat every individual. The referee hands out no style points.`]]),
);

// ================================================================ 10 championship
kids.push(
  H1("10. The championship — protocol and results"),
  ...UL([
    "Per commodity: first ~80% of observed months train; final ~20% (minimum 4 months) form the walk-forward exam described in section 7.2.",
    "Each model self-tunes only on a validation tail inside the training window; ensemble weights learn only on an inner slice of training.",
    "Every exam prediction crosses the true gap to the next real purchase — multi-step forecasts, scored against real months only.",
    "Champion = lowest exam MAPE (RMSE tie-break, ≥70% coverage). The champion is refit on the full history to produce the production forecasts, with uncertainty bands built from its own exam-error distribution, widened with horizon as q80 × √h.",
  ]),
  T(["Championship snapshot", "Value"], [
    ["Commodities refereed", String(S.modelable)],
    ["Distinct winning algorithms", String(S.n_champ_models)],
    ["Most titles", `${S.top_champ} (${S.top_champ_n})`],
    ["Simple-baseline titles", String(S.baseline_wins)],
    ["Ensemble titles", String(S.ensemble_wins)],
    ["Median / q25 / q75 champion MAPE", `${S.mape_med}% / ${S.mape_q25}% / ${S.mape_q75}%`],
  ], [4200, 5160]),
  FIG("Champion-model frequency and MAPE distribution",
      "Screenshot the two charts at the top of the Model Lab page (championship bar + MAPE histogram), or re-export them from the executed notebook, section 4."),
  P("Marquee examples: Silico Manganese 5.5% MAPE (moving average), Ferro Silicon 6.6% (naive), Ferro Vanadium 8.2% (seasonal naive), graphite electrodes 1.3% (top-5 ensemble). The complete table for all commodities is Appendix A."),
);

// ================================================================ 11 fuzzy
const F = S.fuzzy_example;
kids.push(
  H1("11. Fuzzy logic and the Mamdani engine — from zero to our verdicts"),
  H2("11.1 Why ordinary (crisp) logic fails at buying decisions"),
  P("Classical logic is binary: a statement is true or false. 'Prices are rising' must be wholly true or wholly false — so a rule like 'IF prices are rising AND stock is low THEN buy' snaps violently between doing nothing and full alarm as a number crosses an arbitrary threshold. Human buyers don't think that way; they reason in degrees: prices are rising a bit, stock is fairly low, so lean toward buying."),
  H2("11.2 Fuzzy sets and membership — truth in degrees"),
  P("Lotfi Zadeh's 1965 insight: let statements be true to a degree between 0 and 1. 'Prices are rising' becomes a membership function — a curve mapping the actual forecast move to a truth degree. In this project the curves are trapezoids: flat at fully-false, a straight ramp, flat at fully-true. Example, the 'rising' set over the 3-month forecast move: 0 below +2%, ramping up between +2% and +6%, 1 above +6%. A forecast of +4% is 'rising' to degree 0.5 — half-true, and that is a meaningful, usable number."),
  EQ("μ_rising(+4%) = 0.5     μ_rising(+1%) = 0     μ_rising(+8%) = 1"),
  FIG("Membership functions",
      "Generate with Prompt 6 in prompts.docx: the falling / flat / rising trapezoids with the μ_rising(+4%) = 0.5 example point marked. (Ten lines of matplotlib also works.)"),
  H2("11.3 Linguistic variables and rules"),
  P("A linguistic variable is an input described by such labelled sets. This engine uses four, all computed from data: expected move (falling / flat / rising), momentum of the last ~6 observed prices (down / flat / up), urgency = months since the last PO ÷ the commodity's own median cycle (low / medium / high), and volatility = coefficient of variation of the last 12 prices (low / high). Knowledge then reads like a buyer talking:"),
  EQ("IF move IS rising AND urgency IS high THEN action IS strong-buy"),
  P("Twelve such rules cover the space (all listed in Appendix C), including the subtle ones — 'IF move IS falling AND urgency IS high THEN neutral' (need stock but prices easing → stagger) and 'IF volatility IS high THEN neutral' (jumpy prices → smaller lots, weight 0.5)."),
  H2("11.4 Mamdani inference — the five steps"),
  P("Ebrahim Mamdani's 1975 method (built to control a steam engine) turns those rules into one number:"),
  ...UL([
    [{ text: "1 · Fuzzify. ", bold: true }, "Push the four crisp inputs through every membership curve to get truth degrees."],
    [{ text: "2 · Fire the rules. ", bold: true }, "A rule's strength = the MINIMUM of its conditions' degrees (fuzzy AND — a chain is as strong as its weakest link), times the rule's weight."],
    [{ text: "3 · Clip. ", bold: true }, "Each fired rule's output set (an action shape on the 0–100 buy-score axis: strong-wait, wait, neutral, buy, strong-buy) is clipped at that rule's strength — a half-convinced rule contributes a half-height shape."],
    [{ text: "4 · Aggregate. ", bold: true }, "Overlay all clipped shapes and take the MAXIMUM at every point (fuzzy OR) — one combined silhouette of the committee's opinion."],
    [{ text: "5 · Defuzzify. ", bold: true }, "Collapse the silhouette to one number at its centre of gravity:"],
  ]),
  EQ("score = Σ(x · μ(x)) ÷ Σ(μ(x))   over the 0–100 axis"),
  P("Score bands map to verdicts: ≥72 BUY NOW, 58–72 BUY/STAGGER, 42–58 MONITOR, 28–42 WAIT, <28 HOLD OFF. And because the fired rules are known, their plain-English texts become the visible reasons — the explanation IS the mechanism, not a commentary on it."),
  FIG("Mamdani inference, end to end",
      "Generate with Prompt 7 in prompts.docx: the two-rule Mamdani grid populated with the live Silico Manganese numbers from Section 11.5, ending at the real score of 65.9."),
  H2("11.5 A live worked example from the plant's data"),
  CALL([
    [{ text: `${F.commodity}, as of ${S.asof}. `, bold: true },
     `Inputs: expected 3-month move ${F.exp_move}% (flat-ish), momentum ${F.momentum}%/month (flat), urgency ${F.urgency} (past the usual cycle — high), volatility ${F.volatility}% (moderate).`],
    [`Rules that fire meaningfully: 'flat move AND high urgency → buy' fires strongly; 'flat AND medium urgency → neutral' fires partially (urgency sits on the high/medium boundary, so both hold partial truth — exactly what fuzzy logic is for).`],
    [`Aggregating the clipped shapes and taking the centroid: score ${F.score} → verdict ${F.label}. The reasons shown to the buyer are the fired rules verbatim: "${F.reasons[0]}"`],
  ]),
  P(`Contrast with Ferro Vanadium the same day: forecast ${S.fv.exp}% over 3 months with an overdue cycle → 'rising AND high urgency → strong-buy' dominates → score ${S.fv.score}, ${S.fv.label}. Same twelve rules, opposite advice — driven entirely by the data.`),
  H2("11.6 Why Mamdani here, and not a neural network"),
  ...UL([
    "Transparency is the requirement: a buyer must defend a decision to an auditor; 'rule 7 fired at strength 0.8' survives that meeting, a hidden layer does not.",
    "The knowledge genuinely is linguistic — buy-timing wisdom comes as sentences, and fuzzy rules encode sentences without distortion.",
    "Graceful degradation: outputs vary smoothly with inputs; no cliff-edges at arbitrary thresholds.",
    "It composes: the hard prediction problem is already solved by the champion models; the fuzzy layer only fuses their output with urgency and volatility — a fusion problem, which is exactly what Mamdani systems are for.",
  ]),
);

// ================================================================ 12 negotiation
kids.push(
  H1("12. Negotiation analytics"),
  P("The plant's own record is the negotiation textbook: every PO carries the price paid and the pre-tender estimate, so the ratio paid ÷ estimate is a measured negotiation outcome — and its quartiles describe what a good, typical and poor close look like for that commodity."),
  ...UL([
    [{ text: "Reference price ", bold: true }, "= quantity-weighted mean of the last six observed months."],
    [{ text: "Target ", bold: true }, "= ½ reference + ½ the 3-month forecast, clipped inside the forecast band — anchored in reality, tilted by the outlook."],
    [{ text: "Opening ask ", bold: true }, "= target × the best-quartile historical ratio (capped at 0.97) — an aggressive but precedented start."],
    [{ text: "Walk-away ", bold: true }, "= min(forecast p90, reference × worst-quartile ratio) — beyond this, re-tender."],
    [{ text: "Quote percentile ", bold: true }, "= where a vendor's number sits in everything ever paid — '82nd percentile' ends arguments."],
    [{ text: "Bargaining power ", bold: true }, "by tender mode (competitive LTE/open tenders ≈ 0.80, single tender ≈ 0.35), driving a game-theory-informed counter-offer that concedes from the opening toward the quote in proportion to the seller's leverage, capped at target — labelled a heuristic, because it is one."],
    [{ text: "Cost of waiting ", bold: true }, "= (quote − forecast at the next cycle) × quantity — the rupee answer to 'should we just wait?'"],
  ]),
);

// ================================================================ 13 inventory
kids.push(
  H1("13. Inventory analytics and the dual PO recommendation"),
  H2("13.1 The classical mathematics"),
  P("Economic order quantity balances two opposing costs — ordering often (paperwork, tendering) versus holding stock (capital, storage):"),
  EQ("EOQ = √( 2 × annual demand × cost per order ÷ holding cost per unit per year )"),
  P("Safety stock buffers demand surprises during the lead time: z × σ(monthly demand) × √(lead time), where z encodes the service level (1.64 for 95%). The reorder point = lead-time demand + safety stock. Every economic input — lead time, service level, ordering cost, carrying rate — is a visible dial in the app, because the SAP export contains none of them."),
  H2("13.2 Stock cover with no stock ledger — the two clocks"),
  P("The register records receipts, not bin levels, so cover is estimated honestly from flow: months of cover bought by the last order = its quantity ÷ trailing 36-month average consumption; cover remaining = that minus months elapsed; stock-out date = when it hits zero; order-by = stock-out minus lead time. This consumption clock sits beside the ordering-rhythm clock (last PO + median historical gap); when they disagree the earlier date wins, and the LOW/MEDIUM/HIGH risk flag fires on whichever is more alarmed."),
  CALL([[{ text: "Worked example — Silico Manganese: ", bold: true },
    "the last order (~5,005 T) bought ≈1.5 months of cover; more has elapsed, so cover is exhausted, the estimated stock-out date has passed, and both clocks flag HIGH."]]),
  H2("13.3 Usual next PO vs the AI suggestion"),
  P("For every commodity the portal now states two complete recommendations side by side. The USUAL one is pure habit: next date = last PO + the median historical gap; quantity = the median historical order size (with its middle-half range) — no models involved, by design, so the buyer sees exactly what autopilot would do. The AI one starts from the earlier safety clock and then lets the price verdict bend it: BUY NOW pulls the date to today, BUY/STAGGER halfway to today, WAIT slides it to the latest safe date so the forecast drop is captured — never past the consumption clock, never before today. Quantity anchors on EOQ, stretches to a full cycle of demand ahead of a rise (capped at 1.5 cycles and 1.5× the historical p75 order), and shrinks to a bridging lot (lead-time demand + safety) ahead of a fall so the balance is bought cheaper later. Each recommendation prints its reasons, and when safety overrides price — cover exhausted during a WAIT — it says so explicitly."),
  H2("13.4 User-set constraints and the staggered ordering plan"),
  P("Three constraints only the buyer can know are editable per commodity, right on the Inventory page: the vendor's minimum ordering quantity (MOQ), the maximum quantity per purchase order, and the plant's holding capacity. They bind everything — the AI quantity is lifted to MOQ, split when it exceeds the per-PO maximum, and paced against capacity headroom — and each intervention states itself as a reason."),
  P("When lots must split — because the verdict says stagger, or the per-PO maximum forces it, or capacity cannot absorb one receipt — the engine emits a concrete tranche schedule as a table: order-by date, expected arrival, quantity and share, the forecast unit price, estimated cost, and the stock cover after each receipt, with a one-line 'why' per tranche. The mechanism is a single transparent rule applied per tranche: compute its feasibility window (earliest arrival = when holding capacity can absorb the lot after the lead time; latest = just before stock would run dry, given all earlier tranches) and buy at the cheapest champion-forecast price inside that window. Rising forecasts naturally pull tranches early, falling ones push them late, dips get caught — one rule covers every market shape. The table closes with the staggered plan's estimated cost against buying everything today and everything at the usual habit date, and prints honest warnings when constraints make the requirement physically unschedulable."),
);

// ================================================================ 14 impact
kids.push(
  H1("14. Measuring the benefit — the impact framework"),
  P("Three lenses, never mixed, each labelled forecast or fact:"),
  ...UL([
    [{ text: "On the table (forecast). ", bold: true },
     "Each live signal's |forecast move| × last price × the cycle volume — the cost difference between buying now and at the forecast price for tonnage the plant will buy anyway. MONITOR signals are excluded; they make no timing claim."],
    [{ text: "Verified ledger (fact, accumulating). ", bold: true },
     "Signals are frozen into an append-only ledger the day they are issued. When a later upload brings an actual purchase ~3 months on, each matures: direction verdict (moves within ±1.5% count as flat, never marked wrong) and rupee verdict — BUY followed = bought at signal-day price instead of the matured price; WAIT followed = deferred to it; gain = difference × stake volume. The counterfactual is the plant's own later price on its own volume."],
    [{ text: "Held-out proof (fact, from the exam). ", bold: true },
     `Every real purchase month in the untouched 20% window replayed as a decision — lock at the last known price or buy on schedule — with the champion's forecast making the call and the month's actual tonnage as the stake. Scored against always-lock, always-wait and perfect foresight on identical months. Result: ${S.hit_rate}% direction hit-rate over ${S.n_calls} calls; ₹${S.saved_vs_best_cr} crore better than the best naive habit; ${S.capture}% of the perfect-foresight ceiling.`],
  ]),
  P("The Impact Tracker page carries the full step-by-step rationale and a live worked example, so the benefit arithmetic is never a black box."),
);

// ================================================================ 15 results
kids.push(
  H1("15. Results at a glance"),
  T(["Dimension", "Result"], [
    ["Data engineered", `${S.rows_priced.toLocaleString("en-IN")} priced lines; ${S.resolved.toLocaleString("en-IN")} corrected; ${S.rows_dropped} quarantined`],
    ["Coverage", `${S.modelable} commodities under full ML; forecasts at 3/6/12 months with empirical ~80% bands`],
    ["Accuracy", `median MAPE ${S.mape_med}% (q25 ${S.mape_q25}%, q75 ${S.mape_q75}%); ${S.n_champ_models} distinct champions`],
    ["Direction", `${S.hit_rate}% of ${S.n_calls} held-out calls correct`],
    ["Benefit (replay)", `₹${S.saved_vs_best_cr} Cr vs best habit; ₹${S.saved_vs_early_cr} Cr vs always-lock; ${S.capture}% of perfect timing`],
    ["Live", `${S.live_calls} open calls ≈ ₹${S.on_table_cr} Cr at stake (forecast); ${S.ratio_below}% of orders historically close at/below estimate`],
  ], [2400, 6960]),
);

// ================================================================ 16 app pages
const page = (name, what, shot) => [
  H3(name), P(what, { after: 90 }), FIG(`${name} — screenshot`, shot),
];
kids.push(
  H1("16. The application, page by page"),
  P("Nine pages, one narrative: see the portfolio, drill into a commodity, negotiate, plan the order, verify the engine, keep it fed. Insert a screenshot in each box (browser full-screen, light theme, a data-rich commodity such as Silico Manganese selected)."),
  ...page("Command Center",
    "The whole portfolio: today's headline call, spend and signal counters, and the sortable action board — verdict, score, 24-month sparkline, forecast move, cycle position and spend for every covered commodity. Clicking a row opens its deep-dive.",
    "Capture the full page including the headline-call banner and the top of the action board."),
  ...page("Commodity Deep-Dive",
    "The verdict with its reasons and gauge, the order-plan line (usual vs AI), forecast tabs at 3/6/12 months with the uncertainty band, seasonality heat-map, consumption rhythm, PO history with provenance flags, and the Price-arithmetic tab that shows every computation.",
    "Two captures work well: the verdict + 3-month forecast, and the Price-arithmetic tab."),
  ...page("Negotiation Room",
    "Opening / target / walk-away bands over the real price history, quote assessment with percentile, suggested counter, cost of waiting, and data-backed talking points.",
    "Capture with a sample quote entered so the verdict card is visible."),
  ...page("Inventory Planner",
    "EOQ, safety stock, reorder point; cover remaining, stock-out date and the consumption-based order-by beside the historical rhythm; the usual-vs-AI recommendation cards; the all-commodity comparison table; and the order calendar.",
    "Capture the dual recommendation cards plus the first rows of the comparison table."),
  ...page("Impact Tracker",
    "The three lenses with the step-by-step benefit rationale and worked example; strategy-cost comparison and cumulative-advantage charts.",
    "Capture the KPI row and the held-out proof tab."),
  ...page("Model Lab",
    "Championship distribution, the full per-commodity leaderboard, the champion's held-out test chart, and the data-quality quarantine.",
    "Capture the championship chart plus one commodity's actual-vs-predicted test window."),
  P("Four further pages complete the set: the Forecast Registry (one row per commodity — champion model, its method in plain words, held-out MAPE/RMSE/MASE, and a 0–100 confidence score computed from accuracy, reliability-vs-naive and evidence, with the formula printed beside the table), Market Pulse (external benchmarks with a hard time budget so the page always renders in seconds, per-series diagnostics, a connectivity test, a plant-network SSL mode, and a benchmark-to-commodity impact map grouped into Indian market signals — Nifty Metal, Nifty Commodities, Nifty Energy, Nifty Infrastructure, Nifty 50 and the Sensex, read as demand-side and domestic cost sentiment — and global cost benchmarks; each index lists the plant commodities it plausibly touches, the transmission mechanism, and the measured lead-lag correlation where data overlaps), How It Works (this report's story live in the app with current accuracy), and Admin (the drag-and-drop update flow and audit trail, covered next).", { after: 60 }),
);

// ================================================================ 17 learning loop
kids.push(
  H1("17. Self-learning: data refresh, incremental retraining, audit"),
  ...UL([
    [{ text: "Upload. ", bold: true }, "Drag the latest SAP export onto the Admin page; it is validated against the twelve-column layout and fingerprinted (SHA-256)."],
    [{ text: "Merge, safely. ", bold: true }, "Reconciliation is group-wise on (PO No, material, PR): the file's version of a group replaces the stored one (how delivery-quantity revisions flow in), groups absent from the file are kept (a partial extract can never erase history), and re-uploading an applied file is a recognised no-op."],
    [{ text: "Retrain, incrementally. ", bold: true }, "Only commodities whose data changed are re-refereed — a monthly refresh finishes in minutes, not the full twenty."],
    [{ text: "Audit, always. ", bold: true }, "An append-only trail records who, when, the fingerprint, rows added/updated, models retrained and duration; accepted files are archived byte-for-byte; the previous master is backed up. Signals are snapshotted at the same moment, arming the impact ledger."],
  ]),
  FIG("AS-IS and TO-BE workflows",
      "Insert the two flowcharts generated with prompts.docx (also placed in the Explainer, section 5) — AS-IS above, TO-BE below."),
);

// ================================================================ 18-20
kids.push(
  H1("18. Deployment and operations"),
  P("The repository (code + data + artifacts, ~13 MB) lives in a private GitHub repository; Streamlit Community Cloud serves the app free and redeploys automatically on every push. A browser-only path exists for both first deployment and monthly refreshes. The step-by-step, with troubleshooting, is the companion Deployment Guide; the two-minute health check is `python smoke_test.py`."),
  H1("19. Honest limitations"),
  ...UL([
    "PO prices are contract events, not daily quotes — between orders the true market is unobserved, and forecasts inherit that granularity.",
    "Forecasts assume continuity of specification, tender practice and supplier base; a regime change resets the learning until new data accumulates.",
    "No stock ledger exists in the export — cover, stock-out dates and order-by dates are labelled estimates from receipt flow, with assumptions as dials.",
    "Long-tail materials (median " + S.median_pos_per_material + " POs in " + S.years + " years) get descriptive truth, not forecasts.",
    "External benchmarks depend on free public feeds; the panel shows source, age and exact errors rather than ever inventing a number.",
  ]),
  H1("20. Roadmap"),
  ...UL([
    "One-click printable negotiation brief (PDF) per commodity.",
    "What-if sandbox for split-lot timing strategies.",
    "Watchlists and a weekly digest; band-breach and overdue alerts on the Command Center.",
    "Buyer-vs-engine forecast challenge log; per-buyer closed-PO performance view.",
    "Vendor-level analytics once a supplier column is exported; direct SAP integration to retire manual export.",
    "Exogenous features from Market Pulse's lead-lag winners feeding the champions.",
  ]),
);

// ================================================================ 21 glossary
kids.push(
  H1("21. Glossary"),
  T(["Term", "Meaning here"], [
    ["Time series", "Values in time order — one price per month per commodity."],
    ["Lag / rolling feature", "The value k months ago / the average or spread over a recent window — the raw material ML models learn from."],
    ["Walk-forward test", "Standing at past moments and predicting only what came after; the fair exam for forecasters."],
    ["MAPE / RMSE / MASE", "Average % miss / rupee miss with big blunders punished / miss relative to naive (below 1.0 beats naive)."],
    ["Champion", "The model that won a commodity's exam and now makes its forecasts."],
    ["Ensemble", "A weighted blend of models; wins only when the blend beats every individual."],
    ["Simulated annealing", "An optimiser that occasionally accepts worse solutions early (high 'temperature') to escape local traps, settling as it cools."],
    ["Fuzzy set / membership", "Truth in degrees: a curve mapping a number to how true a statement is, 0–1."],
    ["Mamdani inference", "Fuzzify → fire rules (min) → clip outputs → aggregate (max) → centroid: sentences in, one defensible score out."],
    ["Defuzzification / centroid", "Collapsing the aggregated fuzzy opinion to one number at its centre of gravity."],
    ["EOQ / safety stock / reorder point", "Economic lot size / buffer for surprises during lead time / the trigger level."],
    ["Two clocks", "Ordering-rhythm date (habit) vs consumption date (estimated cover) — the earlier one governs."],
    ["Provenance flag", "The tag on every cleaned price recording exactly how it was derived or corrected."],
    ["Signal ledger", "Append-only snapshots of every recommendation, later scored against actual prices."],
    ["Audit trail", "Who uploaded what, when, its fingerprint, and exactly what changed."],
  ], [2600, 6760]),
);

// ================================================================ appendix A
kids.push(
  new Paragraph({ children: [new PageBreak()] }),
  H1("Appendix A — Commodity-by-commodity prediction scorecard"),
  P("One row per covered commodity, ordered by total spend. All values regenerate on every retrain.", { after: 130 }),
  new Table({
    width: { size: 9460, type: WidthType.DXA },
    columnWidths: [3260, 2380, 800, 1150, 800, 700],
    borders: {
      top: { style: BorderStyle.SINGLE, size: 6, color: "C9C9C9" },
      bottom: { style: BorderStyle.SINGLE, size: 6, color: "C9C9C9" },
      left: { style: BorderStyle.SINGLE, size: 4, color: "E0E0E0" },
      right: { style: BorderStyle.SINGLE, size: 4, color: "E0E0E0" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: "ECECEC" },
      insideVertical: { style: BorderStyle.SINGLE, size: 4, color: "ECECEC" },
    },
    rows: [
      new TableRow({ tableHeader: true, children:
        ["Commodity", "Champion model", "MAPE %", "RMSE (₹)", "MASE", "Test"]
        .map((t, i) => new TableCell({
          width: { size: [3260,2380,800,1150,800,700][i], type: WidthType.DXA },
          shading: { type: ShadingType.CLEAR, fill: "EFE6DF" },
          margins: { top: 70, bottom: 70, left: 100, right: 100 },
          children: [new Paragraph({ children: [new TextRun({ text: t,
            font: FONT, size: 19, bold: true, color: INK })] })] })) }),
      ...S.scorecard.map(r => new TableRow({ children: r.map((v, i) =>
        new TableCell({
          width: { size: [3260,2380,800,1150,800,700][i], type: WidthType.DXA },
          margins: { top: 55, bottom: 55, left: 100, right: 100 },
          children: [new Paragraph({ children: [new TextRun({
            text: (i === 3 ? Number(v).toLocaleString("en-IN") : String(v)),
            font: i === 0 ? MONO : FONT, size: i === 0 ? 16 : 18,
            color: INK })] })] })) })),
    ],
  }),
);

// ================================================================ appendix B
kids.push(
  new Paragraph({ children: [new PageBreak()] }),
  H1("Appendix B — Dataset column dictionary"),
  T(["Column", "Meaning", "Role in the engine"], [
    [[{ text: "Material Code", mono: true }], "SAP material number (leading zeros / N-prefix variants occur)", "Identity, normalised for merging"],
    [[{ text: "Material Description", mono: true }], "Human-readable material name", "The commodity key all analytics group on"],
    [[{ text: "PR Number", mono: true }], "Purchase-requisition number", "Part of the merge key; links estimate to order"],
    [[{ text: "PO No", mono: true }], "Purchase-order number", "Merge key; one PO can carry many lines"],
    [[{ text: "PO Date", mono: true }], "Order date", "The time axis of every series"],
    [[{ text: "Quantity Received", mono: true }], "Quantity booked in so far (grows with partial deliveries)", "Weight for monthly prices; consumption proxy; the source of the partial-delivery trap"],
    [[{ text: "PO Rel Date", mono: true }], "PO release date", "Reference only"],
    [[{ text: "Total PO Value", mono: true }], "Full order value in ₹", "Numerator of unit price; spend analytics"],
    [[{ text: "PO Group", mono: true }], "Purchasing group", "Reference only"],
    [[{ text: "PR Est Value / PR Qty.", mono: true }], "Pre-tender estimated value and quantity", "Estimate rate for validation and fallback pricing; negotiation-ratio denominator"],
    [[{ text: "Ordering Mode", mono: true }], "Tender mode (LTE, OT/GTE, single tender, …)", "Bargaining-power weight in the Negotiation Room"],
  ], [2100, 3500, 3760]),
);

// ================================================================ appendix C
kids.push(
  H1("Appendix C — The full fuzzy rule base"),
  P("Rule strength = min of the condition memberships × weight; '—' means the input plays no role in that rule.", { after: 130 }),
  T(["#", "Move", "Momentum", "Urgency", "Volatility", "→ Action", "Wt"], [
    ["1", "rising", "—", "high", "—", "strong-buy", "1.0"],
    ["2", "rising", "—", "medium", "—", "buy", "1.0"],
    ["3", "rising", "—", "low", "—", "buy", "0.8"],
    ["4", "falling", "—", "low", "—", "strong-wait", "1.0"],
    ["5", "falling", "—", "medium", "—", "wait", "1.0"],
    ["6", "falling", "—", "high", "—", "neutral", "1.0"],
    ["7", "flat", "—", "high", "—", "buy", "1.0"],
    ["8", "flat", "—", "medium", "—", "neutral", "0.9"],
    ["9", "flat", "—", "low", "—", "wait", "0.8"],
    ["10", "rising", "up", "—", "—", "strong-buy", "0.7"],
    ["11", "falling", "down", "—", "—", "strong-wait", "0.7"],
    ["12", "—", "—", "—", "high", "neutral", "0.5"],
  ], [520, 1300, 1450, 1350, 1450, 2000, 700]),
  P("Output sets on the 0–100 score axis: strong-wait (peak ~12), wait (~34), neutral (50), buy (~66), strong-buy (~88). Verdict bands: ≥72 BUY NOW · 58–72 BUY/STAGGER · 42–58 MONITOR · 28–42 WAIT · <28 HOLD OFF.", { after: 60 }),
  new Paragraph({ spacing: { before: 340 },
    border: { top: { style: BorderStyle.SINGLE, size: 8, color: "D8D8D8" } },
    children: [new TextRun({
      text: "DSP Commodity Intelligence · Full Project Report · SDTD, Pravartanam · regenerates with live figures on every retrain",
      font: FONT, size: 18, color: MUTE })] }),
);

const doc = new Document({
  numbering: { config: numbering },
  styles: { default: { document: { run: { font: FONT, size: 22, color: INK } } } },
  sections: [{ properties: { page: { margin: {
    top: convertInchesToTwip(0.9), bottom: convertInchesToTwip(0.9),
    left: convertInchesToTwip(1.0), right: convertInchesToTwip(1.0) } } },
    children: kids }],
});

Packer.toBuffer(doc).then(b => {
  fs.writeFileSync("docs/DSP_Commodity_Intelligence_Project_Report.docx", b);
  console.log("report written:", b.length, "bytes, figures:", FIGN);
});
