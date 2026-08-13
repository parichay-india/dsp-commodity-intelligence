const fs = require("fs");
const S = JSON.parse(fs.readFileSync("/tmp/explainer_stats.json", "utf8"));
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  LevelFormat, PageBreak, convertInchesToTwip, HeightRule, AlignmentType,
} = require("docx");

const ACCENT = "C0501F", INK = "1A1A1A", MUTE = "5A6470";
const FONT = "Arial", MONO = "Consolas";

const p = (text, o = {}) => new Paragraph({
  spacing: { after: o.after ?? 170 },
  children: [new TextRun({ text, font: FONT, size: o.size ?? 22,
    bold: o.bold, italics: o.italics, color: o.color ?? INK })],
});
const rich = (runs, o = {}) => new Paragraph({
  spacing: { after: o.after ?? 170 },
  children: runs.map(r => (typeof r === "string" ? { text: r } : r))
    .map(r => new TextRun({ font: r.mono ? MONO : FONT, size: r.size ?? 22,
      color: r.color ?? INK, ...r })),
});
const h1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1,
  spacing: { before: 360, after: 200 },
  children: [new TextRun({ text: t, font: FONT, size: 30, bold: true, color: ACCENT })] });
const h2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2,
  spacing: { before: 240, after: 130 },
  children: [new TextRun({ text: t, font: FONT, size: 25, bold: true, color: INK })] });

const numbering = [
  { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
    style: { paragraph: { indent: { left: 420, hanging: 260 } },
             run: { color: ACCENT } } }] },
];
const bullets = items => items.map(it => new Paragraph({
  numbering: { reference: "bul", level: 0 }, spacing: { after: 110 },
  children: (Array.isArray(it) ? it : [it])
    .map(r => (typeof r === "string" ? { text: r } : r))
    .map(r => new TextRun({ font: r.mono ? MONO : FONT, size: r.size ?? 22,
      color: r.color ?? INK, ...r })),
}));

const callout = lines => new Table({
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
    children: lines.map(l => new Paragraph({
      spacing: { after: 70 },
      children: (Array.isArray(l) ? l : [l])
        .map(r => (typeof r === "string" ? { text: r } : r))
        .map(r => new TextRun({ font: FONT, size: r.size ?? 22,
          color: r.color ?? INK, ...r })),
    })),
  })] })],
});

const table2 = (head, rows, w = [2900, 6460]) => new Table({
  width: { size: w[0] + w[1], type: WidthType.DXA }, columnWidths: w,
  borders: {
    top: { style: BorderStyle.SINGLE, size: 6, color: "C9C9C9" },
    bottom: { style: BorderStyle.SINGLE, size: 6, color: "C9C9C9" },
    left: { style: BorderStyle.SINGLE, size: 4, color: "E0E0E0" },
    right: { style: BorderStyle.SINGLE, size: 4, color: "E0E0E0" },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: "E6E6E6" },
    insideVertical: { style: BorderStyle.SINGLE, size: 4, color: "E6E6E6" },
  },
  rows: [
    new TableRow({ tableHeader: true, children: head.map((t, i) => new TableCell({
      width: { size: w[i], type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: "EFE6DF" },
      margins: { top: 90, bottom: 90, left: 140, right: 140 },
      children: [new Paragraph({ children: [new TextRun({
        text: t, font: FONT, size: 21, bold: true, color: INK })] })] })) }),
    ...rows.map(r => new TableRow({ children: r.map((cell, i) => new TableCell({
      width: { size: w[i], type: WidthType.DXA },
      margins: { top: 80, bottom: 80, left: 140, right: 140 },
      children: [new Paragraph({ children:
        (Array.isArray(cell) ? cell : [cell])
          .map(run => (typeof run === "string" ? { text: run } : run))
          .map(run => new TextRun({ font: run.mono ? MONO : FONT,
            size: run.mono ? 19 : 21, color: run.color ?? INK, ...run })) })],
    })) })),
  ],
});

const placeholder = (label, sub) => new Table({
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
    height: { value: 4600, rule: HeightRule.ATLEAST },
    children: [new TableCell({
      width: { size: 9360, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: "FAF8F5" },
      verticalAlign: "center",
      margins: { top: 200, bottom: 200, left: 200, right: 200 },
      children: [
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 90 },
          children: [new TextRun({ text: label, font: FONT, size: 26,
            bold: true, color: MUTE })] }),
        new Paragraph({ alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: sub, font: FONT, size: 20,
            italics: true, color: MUTE })] }),
      ],
    })],
  })],
});

const children = [];

// title block
children.push(
  p("SAIL — DURGAPUR STEEL PLANT", { size: 20, color: MUTE, after: 60 }),
  new Paragraph({ spacing: { after: 80 }, children: [new TextRun({
    text: "DSP Commodity Intelligence", font: FONT, size: 52, bold: true,
    color: ACCENT })] }),
  p("The Whats and Hows — a plain-language explainer", { size: 26, after: 40 }),
  p("For anyone who wants to understand this project without a data-science background", { size: 21, color: MUTE, after: 40 }),
  p(`Pravartanam · SAIL Digital Transformation Division · data as of ${S.asof}`,
    { size: 20, color: MUTE, after: 300 }),
  new Paragraph({ spacing: { after: 280 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 10, color: ACCENT } },
    children: [new TextRun({ text: " ", size: 2 })] }),
);

// 1 what
children.push(
  h1("1. What is this, in one breath"),
  p("It is a decision assistant for the people who buy the plant's raw materials and spares. It reads eleven and a half years of Durgapur Steel Plant's own purchase orders, learns how each commodity's price behaves, and then answers the three questions every buyer faces: when should we buy, what price is fair, and how much should we order. It runs as a website — open a browser, and every commodity shows a clear verdict like BUY NOW or WAIT, with the reasons written in plain English underneath."),
  callout([
    [{ text: "The one-line pitch: ", bold: true },
     "it replaces gut-feel purchase timing with evidence — and shows its working every single time."],
  ]),
);

// 2 problem
children.push(
  h1("2. The problem it solves"),
  p("A steel plant buys thousands of different materials — ferro alloys, refractories, electrodes, spares, consumables. Their prices move constantly, and the movements matter: the plant spends roughly " + `₹${S.spend12_cr.toLocaleString("en-IN")} crore a year on this basket.` ),
  p("The person negotiating a purchase usually has none of the following at hand: what the plant paid the last five times, whether the price is trending up or down, whether waiting a month would likely be cheaper, what a fair counter-offer looks like, or whether stock is about to run uncomfortably low. Those answers exist — buried across " + `${S.rows_raw.toLocaleString("en-IN")} rows of SAP records — but no human can hold them in their head for ${S.materials.toLocaleString("en-IN")} materials at once.`),
  p("So decisions default to habit and instinct. Buy when the requisition lands. Accept a quote if it looks roughly like last time. That works — until the market moves, and the plant pays for the timing it never chose deliberately."),
);

// 3 dataset
children.push(
  h1("3. The data it learns from"),
  p("Everything begins with one SAP export — the purchase-order register. No external database, no manual data entry, no assumptions typed in by anyone."),
  table2(["Fact", "Value"], [
    ["Purchase-order lines", `${S.rows_raw.toLocaleString("en-IN")} (${S.rows_priced.toLocaleString("en-IN")} usable after cleaning)`],
    ["Period covered", `${S.span[0]} to ${S.span[1]} — ${S.years} years`],
    ["Distinct materials", `${S.materials.toLocaleString("en-IN")}`],
    ["Total spend in the record", `₹${S.total_spend_cr.toLocaleString("en-IN")} crore`],
    ["Biggest items", S.top_spend.map(t => `${t[0]} (₹${t[1].toLocaleString("en-IN")} Cr)`).join(" · ")],
    ["What each row holds", "material, dates, quantity received, PO value, the plant's own estimate, tender mode"],
  ]),
  h2("3.1 The trap hiding in the data — and why cleaning matters"),
  p("A unit price looks trivial: divide the PO value by the quantity received. But for recent orders the receipt is often partial while the recorded value covers the full order — the naive division then invents a price spike that never happened."),
  callout([
    [{ text: "A real example. ", bold: true },
     `In May 2026 the register appears to show Silico Manganese at ₹${S.simn_fake} per tonne — two to three times the market. The truth: only part of the tonnage had arrived against the full order value. The engine catches this, cross-checks against the plant's own estimate, and recovers the genuine rate of ₹${S.simn_true}.`],
    [`Across the whole register, ${S.resolved.toLocaleString("en-IN")} such distorted lines were corrected — each carrying a visible flag saying how — and ${S.rows_dropped} lines that could not be defended were set aside in a quarantine file anyone can inspect. Nothing is silently altered, and nothing questionable feeds the models.`],
  ]),
  p(`One more honest fact about the data: the typical material was bought only ${S.median_pos_per_material} times in ${S.years} years. Meaningful forecasting needs history, so the ${S.modelable} materials with enough of it (at least 20 priced orders across 12+ months) get the full AI treatment — together they cover the lion's share of spend — while the long tail gets clear descriptive analytics instead of made-up forecasts.`),
);

// 4 how AI works
children.push(
  new Paragraph({ children: [new PageBreak()] }),
  h1("4. How the AI/ML actually works — no jargon"),
  h2("4.1 A tournament, not an oracle"),
  p("Machine learning here is not one mysterious brain. It is nineteen different forecasting methods — some very simple (\u201cassume next month looks like last month\u201d), some seasonal, some full machine-learning models that hunt for patterns across lags and calendar months — plus four \u201cteam\u201d blends that combine the best individuals. All twenty-three compete separately on every single commodity."),
  h2("4.2 The exam is rigged to be fair"),
  p("Each competitor studies only the first ~80% of a commodity's history, then sits an exam on the final ~20% — months it has never seen. The exam works exactly like real life: stand at a point in time, predict the price of the next actual purchase (even if that purchase came four months later), then move forward and repeat. Three anti-cheating rules are enforced ruthlessly: no model ever sees the future, gaps between purchases are filled using past information only, and accuracy is scored solely against months where a real purchase happened."),
  h2("4.3 Whoever wins, rules — even if it's the simple one"),
  p(`The winner of each commodity's exam becomes its champion and makes its forecasts. The result is honest and a little humbling: ${S.n_champ_models} different methods hold championships. \u201c${S.top_champ}\u201d leads with ${S.top_champ_n} titles, plain-common-sense baselines hold ${S.baseline_wins}, and the fancy blends earned ${S.ensemble_wins}. When a simple method genuinely predicts a commodity best, this system says so instead of hiding it — that is a feature, not an embarrassment.`),
  h2("4.4 From forecast to advice a human can act on"),
  p("A forecast alone doesn't tell a buyer what to do. A second layer — fuzzy logic, a decades-old technique for turning several soft truths into one firm judgement — weighs four things together: where the price is heading, its recent momentum, how overdue the ordering cycle is, and how jumpy the price has been. Out comes a 0–100 buy-timing score, a verdict (BUY NOW, BUY/STAGGER, MONITOR, WAIT, HOLD OFF), and, crucially, the reasons in plain sentences: \u201cPrices expected to rise and the ordering cycle is overdue — cover now.\u201d"),
  p("Around that sit two more practical layers: negotiation bands (an opening ask, a target, a walk-away — built from the plant's own record of what it historically paid versus its own estimates, adjusted by how competitive the tender mode is) and inventory arithmetic (how much to order, safety stock, and the date to order by — with every assumption shown as an adjustable dial, never a hidden constant)."),
  h2("4.5 It keeps learning — and keeps score on itself"),
  p("Drop a fresh SAP export onto the Admin page and the engine merges it safely (new lines added, revised lines updated, history never erased), re-runs the tournament only for commodities whose data changed, and logs the whole event to an audit trail. And every recommendation is snapshotted the day it is issued: as later uploads bring the actual prices, the Impact Tracker checks each call against reality and grows a cumulative rupee ledger of what following the engine earned. The tool grades its own homework, in public."),
  h2("4.6 Inventory status and stock-out dates — honestly, with no stock ledger"),
  p("The SAP purchase register records what arrives, not what sits in the bin — so the engine estimates stock cover from the receipt flow itself and says so plainly. The arithmetic: the last replenishment quantity ÷ the trailing 36-month average monthly consumption (receipts as the proxy) = months of cover that order bought; subtract the months elapsed since it arrived = estimated cover remaining. Cover reaching zero gives the expected stock-out date, and stepping back by the lead time gives the suggested order-by date."),
  p("The portal shows two clocks side by side for every commodity: this consumption clock, and the ordering-rhythm clock (when the plant historically places the next PO). When they disagree, the earlier date wins, and the risk flag (LOW / MEDIUM / HIGH) fires on whichever clock is more alarmed. Lead time, service level and cost rates stay as visible dials, because the data contains none of them — an estimate that admits it is an estimate is worth more than a confident guess. The buyer can further set, per commodity, the vendor's minimum ordering quantity, a maximum per purchase order, and the plant's holding capacity — the planner treats these as hard rails, splitting large requirements into a staggered tranche schedule that buys each lot at the cheapest forecast point its window allows."),
  callout([
    [{ text: "Worked example — Silico Manganese (as of " + S.asof + "): ", bold: true },
     "the last order of about 5,005 T covers roughly 1.5 months at the trailing consumption rate; more than that has already elapsed, so estimated cover is exhausted, the stock-out date has passed, and both clocks flag the commodity HIGH — order now. This is precisely the early warning a buyer cannot assemble by hand across a hundred materials."],
  ]),
);

// 5 workflows
children.push(
  h1("5. The workflow, before and after"),
  p("Two flowcharts tell the transformation story at a glance: how procurement runs today, and how it runs with the engine standing beside the buyer. They are generated separately (image-generation prompts are supplied in the companion file prompts.docx) and placed here."),
  placeholder("[ Placeholder — Flowchart 1 ]",
    "AS-IS: Commodity Procurement Workflow — generate with Prompt 1 in prompts.docx and insert here (landscape, full width)"),
  p("", { after: 120 }),
  placeholder("[ Placeholder — Flowchart 2 ]",
    "TO-BE: Procurement with the Commodity Price Prediction Engine — generate with Prompt 2 in prompts.docx and insert here (landscape, full width)"),
  p("Reading the pair: every grey step in the first chart survives in the second — the engine deletes no one's job. What changes is what the buyer knows at each step: a verdict with reasons before picking up the PR, price arithmetic behind every figure, fair-price bands in the negotiation, two inventory clocks instead of surprises, and an impact ledger that audits the engine itself.", { italics: true, color: MUTE }),
);

// 5 accuracy
children.push(
  h1("6. How accurate is it — measured, not claimed"),
  p("Every number below comes from the held-out exam months the models never saw, and every one recomputes automatically when new data arrives."),
  table2(["Question", "Measured answer"], [
    ["How close are the price forecasts?", `Median error ${S.mape_med}% — half the commodities forecast better than that (best quartile ${S.mape_q25}%, hardest quartile ${S.mape_q75}%). In practice: the typical 1–4 month call lands within a few percent of the eventual PO rate.`],
    ["Does it call the direction right?", `${S.hit_rate}% of ${S.n_calls} up/down calls on unseen months were correct.`],
    ["What was that worth in rupees?", `Replaying ${S.n_events} real purchase months as timing decisions: following the engine beat the best naive habit by ₹${S.saved_vs_best_cr} crore, and beat \u201calways lock a price immediately\u201d by ₹${S.saved_vs_early_cr} crore — on the same months and the same actual tonnages.`],
    ["How close to perfect timing?", `It captured ${S.capture}% of what a buyer with perfect foresight could have achieved. (Nobody has perfect foresight; this is the honest ceiling.)`],
    ["What's live right now?", `${S.live_calls} open timing calls worth about ₹${S.on_table_cr} crore over the next quarter if the forecasts land — labelled clearly as a forecast in the app.`],
  ], [2700, 6660]),
  p("The commodity-by-commodity scorecard — champion model, MAPE, RMSE, MASE and test length for all " + S.modelable + " covered materials — is Appendix A at the end of this document.", { after: 140 }),
  p("Forecast charts always carry an uncertainty band — not decorative, but the champion's own measured error on its exam, widened with horizon. Roughly 80% of actual prices fall inside it, because that is what the test measured.", { italics: true, color: MUTE }),
);

// 6 what user sees
children.push(
  h1("7. What the user actually sees"),
  ...bullets([
    [{ text: "Command Center — ", bold: true }, "the whole portfolio on one screen: today's headline call, spend and signal counters, and a sortable action board with a verdict, score, mini price-trend and forecast for every covered commodity. Click a row to dive in."],
    [{ text: "Commodity Deep-Dive — ", bold: true }, "the verdict with its reasons and gauge, forecast charts at 3, 6 and 12 months with the uncertainty band, a seasonality heat-map, consumption rhythm, the full PO history with each price's provenance flag — and a Price-arithmetic tab that shows, number by number, how every unit price, monthly point and forecast band was computed."],
    [{ text: "Negotiation Room — ", bold: true }, "opening ask, target and walk-away for the chosen commodity; type a vendor's quote and get a verdict, the quote's percentile against everything ever paid, a suggested counter, and the cost of waiting one cycle instead."],
    [{ text: "Inventory Planner — ", bold: true }, "order quantity, safety stock, estimated cover remaining, stock-out date and order-by dates beside the historical rhythm; editable per-commodity constraints (vendor MOQ, maximum per PO, holding capacity) that bind every recommendation; and a staggered ordering table — how much per tranche, ordered when, at what forecast price, and why — with cost comparisons against buying all at once."],
    [{ text: "Impact Tracker — ", bold: true }, "money at stake on today's calls, the verified ledger that grows as actuals arrive, the held-out proof of the track record — and a step-by-step 'how every rupee is computed' panel with a worked example, so the benefit maths is never a black box."],
    [{ text: "Market Pulse — ", bold: true }, "Indian market signals (Nifty Metal, Nifty Commodities, Nifty Energy, Nifty Infrastructure, Nifty 50, Sensex) alongside global benchmarks (iron ore, coal, Brent, USD/INR, nickel, zinc, dry-bulk freight and the S&P GSCI) with a benchmark-to-commodity impact map — which plant commodities each index touches, the mechanism, and the measured lead where data allows — plus honest per-series diagnostics and a hard time budget so the page always renders in seconds."],
    [{ text: "Forecast Registry — ", bold: true }, "one row per commodity: the champion model, how that method works in one sentence, its measured accuracy (MAPE, RMSE, MASE, test months) and an honest 0\u2013100 confidence score whose formula is printed on the page."],
    [{ text: "Model Lab — ", bold: true }, "full transparency: every model's exam score per commodity, the champion's test-window chart, and the data-quality quarantine."],
    [{ text: "How It Works — ", bold: true }, "this document's story, live inside the app, with the current accuracy numbers."],
    [{ text: "Admin — ", bold: true }, "drag-and-drop data updates with validation, safe merging, incremental retraining and a who-did-what audit trail."],
  ]),
);

// 7 novelty
children.push(
  h1("8. What's genuinely novel and powerful here"),
  ...bullets([
    [{ text: "A championship per commodity, not one model for everything. ", bold: true }, "Each material gets whatever method demonstrably predicts it best — including humble ones. Most tools pick a single algorithm and hope."],
    [{ text: "A referee that cannot be fooled. ", bold: true }, "Strict chronology, past-only gap filling, blends tuned without ever touching the exam. The accuracy numbers survive scrutiny because the test was designed to be attacked."],
    [{ text: "Cleaning with a paper trail. ", bold: true }, "Every corrected price says how it was corrected; every rejected line sits in a quarantine anyone can open. The Silico Manganese trap alone would have poisoned the biggest item's forecasts."],
    [{ text: "Explanations, not oracle answers. ", bold: true }, "Verdicts state their reasons in sentences; negotiation bands trace to the plant's own record; inventory shows its assumptions as dials."],
    [{ text: "It grades its own homework. ", bold: true }, "Signals are snapshotted at birth and verified against reality as uploads arrive — the project's impact becomes a measured, cumulative number instead of a claim."],
    [{ text: "Self-learning without ceremony. ", bold: true }, "One drag-and-drop refreshes data, retrains exactly what changed in minutes, and writes the audit entry. Champions rotate the moment the data says they should."],
    [{ text: "Honesty as a design rule. ", bold: true }, "No invented numbers anywhere: external feeds show their source and age or an honest empty state; long-tail items get descriptive truth instead of fake forecasts."],
  ]),
);

// 8 observations
children.push(
  h1("9. Key observations from DSP's own data"),
  ...bullets([
    [`Partial-delivery distortion is common enough to matter: ${S.resolved.toLocaleString("en-IN")} PO lines needed price correction — including on the single biggest spend item. Any analysis skipping this step inherits fictional spikes.`],
    [`No algorithm rules the plant: ${S.n_champ_models} different methods won championships across ${S.modelable} commodities. Price behaviour differs by material family — ferro alloys trend, refractories step with contracts, spares barely move.`],
    [`Simple methods won ${S.baseline_wins} championships outright. For sticky, contract-anchored prices, \u201cnext ≈ last\u201d is genuinely hard to beat — knowing where sophistication pays is itself intelligence.`],
    [`The plant's negotiation record is strong: about ${S.ratio_below}% of orders close at or below its own estimate. The bands in the Negotiation Room are built from exactly this record.`],
    [`Ordering rhythm is measurable and actionable: dozens of commodities show a clear historical cycle, which is what powers the urgency input, the overdue flags and the order calendar.`],
    [`The typical material sells ${S.median_pos_per_material} POs in ${S.years} years — a long-tail reality. Concentrating ML where history supports it, and being descriptive elsewhere, is the honest architecture for procurement data.`],
  ]),
);

// 9 stack
children.push(
  new Paragraph({ children: [new PageBreak()] }),
  h1("10. The technology stack, in plain words"),
  table2(["Piece", "What it is and why it's here"], [
    ["Python", "The programming language everything is written in — the standard for data and AI work."],
    ["pandas & NumPy", "The workhorses that read, clean and reshape the 21 thousand PO rows in seconds."],
    ["scikit-learn", "The machine-learning library providing the trainable models (forests, boosting, neural net, and friends)."],
    ["SciPy", "Scientific computing toolkit; supplies the simulated-annealing optimiser that tunes the blended ensembles."],
    ["Custom statistical code", "The classical forecasters (Holt-Winters, Theta and family) written from first principles, so the exact same code runs anywhere — including with no internet."],
    ["Streamlit", "Turns Python into the interactive website — pages, charts, sliders, uploads — without a separate web team."],
    ["Plotly", "The interactive charts: hover, zoom, animate."],
    ["openpyxl", "Reads and writes the SAP Excel files."],
    ["Yahoo Finance, World Bank & ECB feeds", "Free, key-less market sources — Indian indices (Nifty family, Sensex), global commodities via the World Bank Pink Sheet, and USD/INR via the ECB — fetched live and cached."],
    ["GitHub", "Version-controlled home of the code and data — every change tracked, private to SAIL."],
    ["Streamlit Community Cloud", "Free hosting that serves the app from the GitHub repository and redeploys automatically on every update."],
  ], [2500, 6860]),
);

// 10 glossary
children.push(
  h1("11. Ten-second glossary"),
  table2(["Term", "Meaning here"], [
    ["MAPE", "Average forecast miss in per cent. 7% means a ₹100 prediction typically lands within about ₹7 of reality."],
    ["Walk-forward test", "Standing at past points in time and predicting only what came after — the fair way to test a forecaster."],
    ["Champion", "The model that won a commodity's walk-forward exam and now makes its forecasts."],
    ["Ensemble", "A blend of several models' forecasts; earns a championship only when the blend beats every individual."],
    ["Fuzzy logic", "A method for combining several soft judgements (\u201cprices rising-ish\u201d, \u201cstock lowish\u201d) into one firm, explainable verdict."],
    ["Provenance flag", "A tag on every cleaned price recording exactly how it was derived or corrected."],
    ["EOQ / safety stock / reorder point", "Classical inventory formulas: the economic order size, the buffer against surprises, and the level (or date) at which to reorder."],
    ["Audit trail", "The append-only log of every data upload: who, when, what changed, and the file's digital fingerprint."],
  ], [2500, 6860]),
  new Paragraph({ children: [new PageBreak()] }),
  h1("Appendix A — Commodity-by-commodity prediction scorecard"),
  p("One row per covered commodity, ordered by total spend. Champion = the model that won its walk-forward exam; MAPE = mean absolute percentage error on the held-out months; RMSE = root-mean-square error in rupees per unit (scale differs by commodity); MASE = error relative to a naive forecaster (below 1.0 beats naive); Test = number of held-out purchase months scored. All values regenerate on every retrain.", { after: 140 }),
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
  new Paragraph({ spacing: { before: 360 },
    border: { top: { style: BorderStyle.SINGLE, size: 8, color: "D8D8D8" } },
    children: [new TextRun({
      text: "DSP Commodity Intelligence · SDTD, Pravartanam · This explainer regenerates with live figures; companion documents: the Deployment Guide (operations) and the Model Laboratory notebook (full technical audit trail).",
      font: FONT, size: 18, color: MUTE })] }),
);

const doc = new Document({
  numbering: { config: numbering },
  styles: { default: { document: { run: { font: FONT, size: 22, color: INK } } } },
  sections: [{ properties: { page: { margin: {
    top: convertInchesToTwip(0.9), bottom: convertInchesToTwip(0.9),
    left: convertInchesToTwip(1.0), right: convertInchesToTwip(1.0) } } },
    children }],
});

Packer.toBuffer(doc).then(b => {
  fs.writeFileSync("docs/DSP_Commodity_Intelligence_Explainer.docx", b);
  console.log("explainer written:", b.length, "bytes");
});
