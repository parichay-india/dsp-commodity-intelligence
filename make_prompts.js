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

const PROMPT1 = "A clean, professional business-process flowchart, corporate consulting style, flat vector design on a pure white background, landscape 16:9, high resolution, crisp legible sans-serif text, orthogonal right-angled connector arrows in medium grey, generous even spacing, no photos, no clip-art, no 3D, no gradients, no watermark. Title centred at the top in dark charcoal bold text: 'AS-IS: Commodity Procurement Workflow — Durgapur Steel Plant'. Three horizontal swimlanes separated by thin grey lines, labelled vertically on the left edge in grey: 'Indenting Department' (top), 'Purchase Section' (middle), 'Vendor' (bottom). The main flow runs left to right through rounded rectangles filled light grey (#EDEDED) with dark charcoal text, in this exact order with these exact labels: in the top lane 'Material requirement raised (PR in SAP)' with an arrow down into the middle lane to 'PR reaches Purchase Section queue', then 'Buyer picks up PR when due', then 'Estimate looked up from last PO / personal memory', then a pale-yellow decision diamond 'Tender route?' with two labelled branches: branch 'Open / limited tender' goes to 'Float enquiry and wait for quotes', branch 'Single vendor' goes to 'Ask vendor for a quote'; in the bottom lane both branches connect to 'Vendor submits quotation' which arrows back up to the middle lane box 'Negotiation based on experience and gut feel', then 'Purchase order released', then down to the bottom lane 'Vendor delivers material, often in parts', then back up to 'Goods receipt, payment and closure'. From the last box, a thin grey dashed arrow curves back left to the first box, labelled in small grey italic text 'repeats every cycle'. Attach five small red rounded tags with white bold text near the relevant steps, connected by short thin red leader lines: 'No price-trend visibility' near the estimate box, 'Timing set by PR date, not by the market' near the buyer-picks-up box, 'No benchmark for a fair counter-offer' near the negotiation box, 'Stock-out surprises' near the delivery box, 'Knowledge lives in individual heads' near the memory box. All quoted text must appear exactly as written, spelled correctly, large enough to read when printed on A4.";

const PROMPT2 = "A clean, professional business-process flowchart, corporate consulting style, flat vector design on a pure white background, landscape 16:9, high resolution, crisp legible sans-serif text, orthogonal right-angled connector arrows in medium grey, generous even spacing, no photos, no clip-art, no 3D, no watermark. Title centred at the top in dark charcoal bold text: 'TO-BE: Procurement with the Commodity Price Prediction Engine'. Four horizontal swimlanes separated by thin grey lines, labelled vertically on the left edge: 'Indenting Department', 'Purchase Section', 'Commodity Intelligence Engine' (this third lane has a very light orange background tint #FDEBDD), 'Vendor'. Boxes in the engine lane are filled light orange (#F7C59F) with dark charcoal text; all other boxes are light grey (#EDEDED). The flow, left to right, with these exact labels: top lane 'Material requirement raised (PR in SAP)' arrows down to the engine lane box 'Dashboard already shows a verdict: BUY NOW / WAIT, with plain-English reasons', which arrows up to the Purchase Section box 'Buyer opens Command Center — headline call and action board', then 'Deep-dive: 3/6/12-month forecast with uncertainty band and price arithmetic', then a pale-yellow decision diamond 'Engine says WAIT?'. Branch 'Yes' goes right to the grey box 'Defer or stagger the purchase; inventory clocks confirm stock cover' with a dashed grey arrow looping back to the deep-dive box labelled 'monitor'. Branch 'No — buy' continues to 'Negotiation Room: open, target and walk-away bands, quote percentile, suggested counter-offer', then 'Negotiate with data-backed talking points', then 'Purchase order released', then down to the Vendor lane 'Vendor delivers material', then down-left into the engine lane 'Monthly SAP export dragged and dropped — auto-merge, retrain only what changed, audit trail entry', then 'Impact Tracker verifies matured signals; cumulative rupee ledger grows', with a thin orange dashed arrow curving back to the first engine box labelled in small italic 'the engine keeps learning'. Attach five small green rounded tags with white bold text near the relevant steps, connected by short thin green leader lines: 'Timing is chosen, not defaulted' near the Command Center box, '81% direction hit-rate on unseen months' near the deep-dive box, 'Fair-price bands from the plant's own record' near the Negotiation Room box, 'Stock-out date forecast from consumption' near the defer box, 'Every upload audited and reversible' near the SAP-export box. All quoted text must appear exactly as written, spelled correctly, large enough to read when printed on A4.";

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
  p("What it depicts: today's flow across three swimlanes (Indenting Department, Purchase Section, Vendor), from PR to payment, with five red pain-point tags — no price visibility, habit-driven timing, no negotiation benchmark, stock-out surprises, tribal knowledge.", { italics: true, color: MUTE }),
  promptBox(PROMPT1),

  h1("Prompt 2 — TO-BE: With the Commodity Price Prediction Engine"),
  p("What it depicts: the same journey with a fourth, orange 'Commodity Intelligence Engine' swimlane woven in — verdict before pickup, deep-dive and price arithmetic, Negotiation Room bands, inventory clocks on WAIT, drag-and-drop learning loop and the Impact Tracker — with five green benefit tags. Deliberately shows every human step surviving: the engine assists, it does not replace.", { italics: true, color: MUTE }),
  promptBox(PROMPT2),

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
