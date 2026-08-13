const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  LevelFormat, convertInchesToTwip,
} = require("docx");

const ACCENT = "C0501F", INK = "1A1A1A", MUTE = "5A6470";
const FONT = "Arial", MONO = "Consolas";

const p = (text, o = {}) => new Paragraph({
  spacing: { after: o.after ?? 160 },
  children: [new TextRun({ text, font: FONT, size: o.size ?? 22,
    bold: o.bold, italics: o.italics, color: o.color ?? INK })],
});
const h1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1,
  spacing: { before: 340, after: 180 },
  children: [new TextRun({ text: t, font: FONT, size: 29, bold: true, color: ACCENT })] });

const numbering = [
  { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
    style: { paragraph: { indent: { left: 420, hanging: 260 } },
             run: { color: ACCENT } } }] },
];
const bullets = items => items.map(t => new Paragraph({
  numbering: { reference: "bul", level: 0 }, spacing: { after: 100 },
  children: [new TextRun({ text: t, font: FONT, size: 22, color: INK })],
}));

const promptBox = (text) => new Table({
  width: { size: 9360, type: WidthType.DXA }, columnWidths: [9360],
  borders: {
    top: { style: BorderStyle.SINGLE, size: 4, color: "D8D8D8" },
    bottom: { style: BorderStyle.SINGLE, size: 4, color: "D8D8D8" },
    left: { style: BorderStyle.SINGLE, size: 12, color: ACCENT },
    right: { style: BorderStyle.SINGLE, size: 4, color: "D8D8D8" },
    insideHorizontal: { style: BorderStyle.NONE },
    insideVertical: { style: BorderStyle.NONE },
  },
  rows: [new TableRow({ children: [new TableCell({
    width: { size: 9360, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, fill: "F5F3F0" },
    margins: { top: 150, bottom: 150, left: 210, right: 210 },
    children: [new Paragraph({ spacing: { after: 0, line: 300 },
      children: [new TextRun({ text, font: MONO, size: 19, color: "2B2B2B" })],
    })],
  })] })],
});

const PROMPT1 = "A clean, professional business-process flowchart, corporate consulting style, flat vector design on a pure white background, landscape 16:9, high resolution, crisp legible sans-serif text, orthogonal right-angled connector arrows in medium grey, generous even spacing, no photos, no clip-art, no 3D, no gradients, no watermark. Title centred at the top in dark charcoal bold text: 'AS-IS: Materials Management on the SAP/GeM Landscape — Durgapur Steel Plant'. Main procurement chain runs left to right across the upper half as rounded rectangles, in this exact order with these exact labels: 'Production Units' (steel-blue fill, white text) connected by an arrow labelled 'PR' to 'On-line Screening & Approval' (soft pink), then 'Purchasing' (light green), then 'E-Tendering on SAP / GeM' (light green), then 'On-line Offer Submission & Tender Evaluation' (soft pink), then 'Order Placement' (light green), then an arrow to a tall rounded rectangle on the right edge labelled 'Vendor / Supplies' (light grey). Middle band: a light-blue rounded rectangle 'Inspection Wing' with three labelled arrows: one coming left from 'Vendor / Supplies' labelled 'On-line IR Submission', one going right back to 'Vendor / Supplies' labelled 'On-line IC Issue', and one going down-left labelled 'Inspection' to the box 'Stores' (golden yellow). Bottom band: 'Stores' has a long right arrow labelled 'GRN Confirmation' to the 'Vendor / Supplies' lane, a left arrow labelled 'Stock Release' returning to 'Production Units', and a thin dashed upward arrow labelled 'PR (stock items)' to 'On-line Screening & Approval'. Below, a white rounded rectangle 'Finance / Accounting' receives a left arrow from 'Vendor / Supplies' labelled 'Bill Submission' and sends a right arrow back labelled 'E-Payment to Vendor'. Attach five small red rounded tags with white bold text near the relevant steps, connected by short thin red leader lines: 'No price-trend visibility' near On-line Screening & Approval; 'Buy timing set by PR arrival, not the market' near Purchasing; 'Quotes judged against estimate and memory — no market benchmark' near On-line Offer Submission & Tender Evaluation; 'Order quantity by habit' near Order Placement; 'Stock-outs discovered, not predicted' near Stores. All quoted text must appear exactly as written, spelled correctly, large enough to read when printed on A4.";

const PROMPT2 = "A clean, professional business-process flowchart, corporate consulting style, flat vector design on a pure white background, landscape 16:9, high resolution, crisp legible sans-serif text, orthogonal right-angled connector arrows in medium grey, generous even spacing, no photos, no clip-art, no 3D, no watermark. Title centred at the top in dark charcoal bold text: 'TO-BE: SAP/GeM Procurement with the Commodity Price Prediction Engine'. Reproduce the identical AS-IS chain in the upper half, same order, same colours, same exact labels: 'Production Units' (steel blue) — arrow 'PR' — 'On-line Screening & Approval' (soft pink) — 'Purchasing' (light green) — 'E-Tendering on SAP / GeM' (light green) — 'On-line Offer Submission & Tender Evaluation' (soft pink) — 'Order Placement' (light green) — 'Vendor / Supplies' (light grey, right edge), with 'Inspection Wing' (light blue, arrows 'On-line IR Submission', 'On-line IC Issue', 'Inspection'), 'Stores' (golden yellow, arrows 'GRN Confirmation', 'Stock Release', dashed 'PR (stock items)'), and 'Finance / Accounting' (white, arrows 'Bill Submission' and 'E-Payment to Vendor'). Beneath everything add a full-width horizontal band with a very light orange background tint (#FDEBDD), labelled vertically on its left edge 'Commodity Intelligence Engine', containing six rounded rectangles filled light orange (#F7C59F) with dark charcoal text, left to right: 'Price forecast per commodity — BUY / WAIT verdict with plain-English reasons', 'Two inventory clocks — stock-out date and order-by date', 'Negotiation bands: open, target, walk-away + quote percentile', 'AI order date and quantity within MOQ, max-per-PO and holding capacity + staggered tranche plan', 'Monthly SAP export drag-and-drop — auto-merge, retrain, audit trail', 'Impact Tracker verifies matured signals — cumulative rupee ledger'. Connect the band to the chain with thin dashed orange arrows: verdict box up to 'Purchasing' labelled 'timing chosen before pickup'; clocks box up to 'Stores' labelled 'no stock-out surprises'; bands box up to 'On-line Offer Submission & Tender Evaluation' labelled 'data-backed evaluation and counter-offer'; AI-order box up to 'Order Placement' labelled 'how much and when, constraints honoured'; a dashed arrow down from 'Stores' to the SAP-upload box labelled 'new SAP data'; and a thin orange dashed arrow curving from the Impact Tracker box back along the band labelled in small italic 'the engine keeps learning'. Attach five small green rounded tags with white bold text near the relevant steps, connected by short thin green leader lines: '81% direction hit-rate on unseen months' near the verdict box; 'Fair-price bands from the plant's own record' near Tender Evaluation; 'Stock-out dates forecast from consumption' near Stores; 'Lots staggered at the cheapest forecast points' near Order Placement; 'Every upload audited, impact measured in rupees' near the SAP-upload box. Every original SAP/GeM step remains unchanged — the engine augments the flow, it replaces nothing. All quoted text must appear exactly as written, spelled correctly, large enough to read when printed on A4.";

const PROMPT3 = "A clean, professional system-architecture block diagram, corporate consulting style, flat vector design on a pure white background, landscape 16:9, high resolution, crisp legible sans-serif text, orthogonal right-angled connector arrows in medium grey with solid arrowheads, generous even spacing, no photos, no clip-art, no 3D, no gradients, no watermark. Title centred at the top in dark charcoal bold text: 'System Architecture — DSP Commodity Intelligence'. A main chain of six rounded rectangles runs left to right, connected by bold grey arrows, with these exact labels: first box 'SAP PO Export (.xlsx) — 21,000+ purchase-order lines' (light grey fill, dark charcoal text); second box 'Data Pipeline — price-resolution cascade with provenance flags · quantity-weighted monthly series · commodity catalog · quarantine' (pale blue-grey); third box 'Bake-off Engine — 19 forecasting models + 4 ensembles · walk-forward referee, no peeking' (light orange #F7C59F); fourth box 'Decision Layer — Mamdani fuzzy verdicts with reasons · negotiation bands · inventory clocks & stagger planner' (light orange #F7C59F); fifth box 'Artifacts Store — champions · forecasts with bands · decision signals · signal ledger · audit trail' (pale blue-grey); sixth box 'Streamlit Dashboard — 10 pages: Command Center, Deep-Dive, Negotiation Room, Inventory Planner, Impact Tracker, Market Pulse, Model Lab, Forecast Registry, How It Works, Admin' (soft green, slightly taller than the others). Above the sixth box, a separate light-blue rounded rectangle labelled 'External Feeds — Yahoo Finance: Nifty family, Sensex, freight, GSCI · World Bank Pink Sheet: global commodities · Frankfurter/ECB: USD/INR' with a downward grey arrow into the Streamlit Dashboard box labelled 'Market Pulse'. Below the sixth box, a small white rounded rectangle with a thin grey border labelled 'Private GitHub repository → Streamlit Community Cloud (free hosting, browser-only workflow)' connected upward to the dashboard by a short grey line labelled 'serves'. A long dashed orange feedback arrow runs from the bottom of the Streamlit Dashboard box, along the bottom of the diagram, back into the Data Pipeline box, labelled in italic dark-orange text: 'Admin drag-and-drop: monthly SAP upload → validate → safe merge → incremental retrain → audit entry → signals snapshotted'. All quoted text must appear exactly as written, spelled correctly, large enough to read when printed on A4.";

const PROMPT4 = "A clean, professional data-flow diagram, corporate consulting style, flat vector design on a pure white background, landscape 16:9, high resolution, crisp legible sans-serif text, orthogonal right-angled connector arrows in medium grey, generous spacing, no photos, no clip-art, no 3D, no watermark. Title centred at the top in dark charcoal bold text: 'Data Pipeline — from raw SAP rows to trustworthy monthly prices'. Flow runs left to right. First box 'Raw PO line — value, quantity received, PR quantity, PR estimate' (light grey). Arrow to box 'Three candidate rates: value ÷ qty received · value ÷ PR qty · PR estimate rate' (pale blue-grey). Arrow to a pale-yellow decision diamond 'Straight PO rate inside the robust band (median ± 3.5 MAD, log scale) and consistent with the estimate?'. Its 'Yes' branch goes right to a green rounded rectangle 'OK — price accepted (19,489 lines)'. Its 'No' branch drops to a second pale-yellow diamond 'Value ÷ PR quantity plausible? (partial delivery)' whose 'Yes' goes right to an amber rounded rectangle 'RESOLVED_PRQTY — re-priced via PR quantity (773 lines)' and whose 'No' drops to a third diamond 'PR estimate rate plausible?' with 'Yes' to an amber rounded rectangle 'RESOLVED_EST — estimate rate used (669 lines)' and 'No' to a red rounded rectangle with white bold text 'QUARANTINE — excluded, kept for audit (510 lines)'; draw this entire quarantine branch, its arrow and box, in red. The three accepted boxes (green and both amber) merge with grey arrows into a single box 'One trustworthy unit price per line, each carrying its provenance flag' (pale blue-grey), then an arrow to 'Quantity-weighted monthly price: Σ(price × qty) ÷ Σ(qty)' (pale blue-grey), then a final arrow to 'Regular monthly grid — gap months filled from PAST observations only, accuracy scored only on real purchase months' (soft green). All quoted text must appear exactly as written, spelled correctly, legible when printed on A4.";

const PROMPT5 = "A clean, professional timeline diagram, corporate consulting style, flat vector design on a pure white background, landscape 16:9, high resolution, crisp legible sans-serif text, no photos, no clip-art, no 3D, no watermark. Title centred at the top in dark charcoal bold text: 'Walk-Forward Evaluation — the exam that cannot be fooled'. A single horizontal timeline axis spans the width, labelled '2015' at the left end and '2026' at the right end. Along the axis, about twenty-five solid dark-grey dots at deliberately IRREGULAR spacing represent observed purchase months — some clustered close together, some separated by visible gaps. The left ~80% of the timeline sits on plain white background labelled above in grey text 'Training window — first ~80% of observed months'; the right ~20% is shaded a very light orange band labelled above in dark-orange bold text 'Exam — never used for training or tuning'. Inside the exam band draw three vertical dashed charcoal cursor lines labelled 'now', each positioned exactly at one dot; from each cursor a curved solid orange arrow leaps rightward over the empty gap to the NEXT dot, the three arrows labelled 'forecast across the true gap: h = 1 month', 'h = 3 months', 'h = 2 months'. Beneath the exam band, small italic grey text: 'stand at a moment in time → predict the next real purchase → reveal the truth → step forward → repeat'. Along the bottom of the diagram a thin footnote strip in grey text: 'Gap months interpolated from the past only · ensemble weights tuned inside training only · accuracy scored solely on months with real purchases'. All quoted text exactly as written, spelled correctly, legible at A4 print size.";

const PROMPT6 = "A clean, minimal mathematical chart, textbook style, flat vector design on a pure white background, landscape 16:9, high resolution, crisp legible sans-serif text, thin dark-grey axes, no photos, no clip-art, no 3D, no gridlines except where specified, no watermark. Title centred at the top in dark charcoal bold text: 'Fuzzy Membership Functions — expected 3-month price move'. A single chart: horizontal axis labelled 'Expected move over 3 months (%)' running from −10 to +10 with tick labels at −10, −6, −4, −2, 0, +2, +4, +6, +10; vertical axis labelled 'Degree of membership μ' from 0 to 1 with ticks at 0, 0.5, 1. Three overlapping trapezoid curves drawn as bold coloured lines with small labels beside them: 'FALLING' in blue — flat at μ=1 from −10 to −6, straight ramp down from (−6, 1) to (−2, 0), then flat at 0; 'FLAT' in grey — 0 up to −4, ramp up from (−4, 0) to (−1, 1), plateau at 1 from −1 to +1, ramp down from (+1, 1) to (+4, 0); 'RISING' in orange — 0 up to +2, straight ramp up from (+2, 0) to (+6, 1), flat at 1 from +6 to +10. Mark the worked example: a vertical dashed charcoal line at +4 rising from the axis, intersecting the orange RISING ramp at height 0.5, with a solid orange dot at that intersection and a short horizontal dashed line from the dot to the vertical axis at 0.5; annotate the dot with the label 'μ_rising(+4%) = 0.5 — half-true, and usable'. All quoted text and numbers exactly as written, spelled correctly, legible at A4 print size.";

const PROMPT7 = "A clean, professional multi-panel mathematical diagram, textbook style, flat vector design on a pure white background, landscape 16:9, high resolution, crisp legible sans-serif text, thin dark-grey axes, no photos, no clip-art, no 3D, no watermark. Title centred at the top in dark charcoal bold text: 'Mamdani Inference — two rules, five steps, one defensible score'. Layout: a 3-row × 3-column grid of small charts with generous spacing. Row 1, labelled on the left edge 'Rule A: IF move IS flat AND urgency IS high THEN buy': column 1 a small chart titled 'move' showing a grey trapezoid membership curve for FLAT over an axis from −10% to +10%, with a vertical dashed line at −1.8% crossing it high, intersection dot labelled '0.9'; column 2 a small chart titled 'urgency' showing an orange rising trapezoid for HIGH over an axis 0 to 2, vertical dashed line at 1.35 crossing it, dot labelled '0.7'; column 3 a small chart titled 'output' with axis 0–100 showing a triangle labelled 'buy' peaking near 66, clipped horizontally at height 0.7 (the filled clipped area shaded light orange), caption beneath 'rule strength = min(0.9, 0.7) = 0.7'. Row 2, labelled 'Rule B: IF move IS flat AND urgency IS medium THEN neutral': same three-chart pattern — FLAT crossed at −1.8% with dot '0.9'; a grey triangular MEDIUM set crossed at 1.35 with a lower dot labelled '0.3'; output triangle labelled 'neutral' centred at 50, clipped at height 0.3, shaded light grey, caption 'rule strength = min(0.9, 0.3) = 0.3'. Row 3, one wide chart spanning all columns titled 'Aggregate (max) and defuzzify (centroid)': the 0–100 axis showing both clipped shapes overlaid, their upper envelope drawn as a bold dark line, the combined silhouette lightly shaded, and a bold vertical orange arrow dropping to the axis at 66 labelled 'centroid → score 65.9 → BUY / STAGGER'. Along the bottom a thin caption strip in grey italic: 'Live example: Silico Manganese — move −1.8%, urgency 1.35 · fuzzify → fire (min) → clip → aggregate (max) → centroid'. All quoted text and numbers exactly as written, spelled correctly, legible at A4 print size.";

const children = [
  p("SAIL — DURGAPUR STEEL PLANT", { size: 20, color: MUTE, after: 60 }),
  new Paragraph({ spacing: { after: 80 }, children: [new TextRun({
    text: "Flowchart Generation Prompts", font: FONT, size: 46, bold: true,
    color: ACCENT })] }),
  p("For Nano Banana (or any capable image model) — AS-IS and TO-BE procurement workflows",
    { size: 24, after: 40 }),
  p("Companion to: DSP Commodity Intelligence Explainer, Section 5 (placeholders provided there)",
    { size: 20, color: MUTE, after: 280 }),
  new Paragraph({ spacing: { after: 260 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 10, color: ACCENT } },
    children: [new TextRun({ text: " ", size: 2 })] }),

  h1("How to use these prompts"),
  ...bullets([
    "Copy one full prompt block below (everything inside the box, as one paragraph) and paste it into Nano Banana. Generate the two charts separately.",
    "Ask for landscape 16:9 at the highest available resolution; both are designed to sit full-width on an A4 page.",
    "Image models sometimes misspell embedded text. If any label comes out wrong, reply with: 'Regenerate the same image; fix only the spelling of the text labels, change nothing else.' One or two rounds usually lands it.",
    "Once satisfied, insert Flowchart 1 and Flowchart 2 into the two dashed placeholder boxes in Section 5 of the Explainer document (Insert → Picture, then size to page width).",
    "Keep the white background — both documents and the portal print cleanly that way.",
  ]),

  h1("Prompt 1 — AS-IS: Commodity Procurement Workflow"),
  p("What it depicts: DSP's actual SAP/GeM materials-management flow, exactly as on the plant's own process board — Production Units raising PRs, on-line screening and approval, Purchasing, e-tendering, on-line offer submission and tender evaluation, order placement, vendor supplies, the Inspection Wing's IR/IC loop, Stores with GRN confirmation and stock release, and Finance with bill submission and e-payment — plus five red tags marking the decision gaps the digital workflow leaves open.", { italics: true, color: MUTE }),
  promptBox(PROMPT1),

  h1("Prompt 2 — TO-BE: With the Commodity Price Prediction Engine"),
  p("What it depicts: the identical SAP/GeM chain, untouched, with an orange 'Commodity Intelligence Engine' band beneath it feeding the decision points — the verdict before Purchasing picks up, the two inventory clocks into Stores, negotiation bands into tender evaluation, the constrained AI order plan into Order Placement, and the learning loop closed by the monthly SAP upload and the Impact Tracker — with five green benefit tags. Every existing step survives; the engine augments, it replaces nothing.", { italics: true, color: MUTE }),
  promptBox(PROMPT2),

  h1("Prompt 3 — System Architecture (Project Report, Figure 2)"),
  p("What it depicts: the whole system on one slide — SAP export through the data pipeline, the orange bake-off engine and decision layer, the artifacts store, and the ten-page dashboard; the three live external feeds entering Market Pulse; the GitHub-to-Streamlit-Cloud hosting block; and the dashed orange self-learning loop from the Admin upload back to the pipeline.", { italics: true, color: MUTE }),
  promptBox(PROMPT3),

  h1("Prompt 4 — Data Pipeline Flow (Project Report, Figure 3)"),
  p("What it depicts: the price-resolution cascade with its three decision diamonds, the red quarantine branch, and the real line counts, flowing into the quantity-weighted monthly series and the past-only grid.", { italics: true, color: MUTE }),
  promptBox(PROMPT4),

  h1("Prompt 5 — Walk-Forward Evaluation (Project Report, Figure 4)"),
  p("What it depicts: the irregular purchase-month timeline, the shaded untouched exam window, and three 'now' cursors forecasting across true gaps — the anti-cheating rules as a footnote strip.", { italics: true, color: MUTE }),
  promptBox(PROMPT5),

  h1("Prompt 6 — Fuzzy Membership Functions (Project Report, Figure 6)"),
  p("What it depicts: the falling / flat / rising trapezoids over the expected-move axis, with the worked example point μ_rising(+4%) = 0.5 marked.", { italics: true, color: MUTE }),
  promptBox(PROMPT6),

  h1("Prompt 7 — Mamdani Inference End to End (Project Report, Figure 7)"),
  p("What it depicts: the classic two-rule Mamdani grid — fuzzify, fire by min, clip, aggregate by max, centroid — populated with the live Silico Manganese numbers from Section 11.5 of the report, ending at the real score of 65.9.", { italics: true, color: MUTE }),
  promptBox(PROMPT7),

  h1("A note on Figure 5 (champion frequency and MAPE distribution)"),
  p("Figure 5 is deliberately NOT generated by an image model: it shows real results — which algorithms won how many championships and the actual error distribution across all covered commodities. Screenshot the two charts at the top of the Model Lab page, or re-export them from section 4 of the executed notebook. Fabricated bars in a results figure would violate the project's no-invented-numbers rule.", { italics: true, color: MUTE }),

  new Paragraph({ spacing: { before: 340 },
    border: { top: { style: BorderStyle.SINGLE, size: 8, color: "D8D8D8" } },
    children: [new TextRun({
      text: "DSP Commodity Intelligence · SDTD, Pravartanam · prompts.docx",
      font: FONT, size: 18, color: MUTE })] }),
];

const doc = new Document({
  numbering: { config: numbering },
  styles: { default: { document: { run: { font: FONT, size: 22, color: INK } } } },
  sections: [{ properties: { page: { margin: {
    top: convertInchesToTwip(0.9), bottom: convertInchesToTwip(0.9),
    left: convertInchesToTwip(1.0), right: convertInchesToTwip(1.0) } } },
    children }],
});

Packer.toBuffer(doc).then(b => {
  fs.writeFileSync("docs/prompts.docx", b);
  console.log("prompts.docx written:", b.length, "bytes");
});
