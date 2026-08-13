const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  LevelFormat, TableOfContents, PageBreak, convertInchesToTwip,
} = require("docx");

const ACCENT = "C0501F";      // molten steel
const INK = "1A1A1A";
const MUTE = "5A6470";
const FONT = "Arial";
const MONO = "Consolas";

const p = (text, opts = {}) => new Paragraph({
  spacing: { after: opts.after ?? 160, before: opts.before ?? 0 },
  alignment: opts.align,
  children: [new TextRun({
    text, font: FONT, size: opts.size ?? 22, bold: opts.bold,
    italics: opts.italics, color: opts.color ?? INK,
  })],
});

const rich = (runs, opts = {}) => new Paragraph({
  spacing: { after: opts.after ?? 160 },
  children: runs.map(r => new TextRun({
    font: r.mono ? MONO : FONT, size: r.size ?? 22, ...r,
    color: r.color ?? INK,
  })),
});

const h1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1,
  spacing: { before: 360, after: 200 },
  children: [new TextRun({ text: t, font: FONT, size: 30, bold: true, color: ACCENT })] });
const h2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2,
  spacing: { before: 260, after: 140 },
  children: [new TextRun({ text: t, font: FONT, size: 25, bold: true, color: INK })] });

const code = (lines) => new Table({
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
    margins: { top: 120, bottom: 120, left: 200, right: 200 },
    children: lines.map(l => new Paragraph({
      spacing: { after: 40 },
      children: [new TextRun({ text: l, font: MONO, size: 19, color: "2B2B2B" })],
    })),
  })] })],
});

const madeRefs = new Set();
const numberedList = (items, ref = null) => {
  if (!ref) { ref = `steps-${madeRefs.size}`; }
  if (!madeRefs.has(ref)) {
    madeRefs.add(ref);
    numbering.push({
      reference: ref,
      levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.",
        style: { paragraph: { indent: { left: 460, hanging: 320 } },
                 run: { bold: true, color: ACCENT } } }],
    });
  }
  return items.map(it => new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 120 },
    children: (Array.isArray(it) ? it : [{ text: it }]).map(r =>
      new TextRun({ font: r.mono ? MONO : FONT, size: r.size ?? 22,
                    color: r.color ?? INK, ...r })),
  }));
};

const bullets = (items) => items.map(it => new Paragraph({
  numbering: { reference: "bul", level: 0 }, spacing: { after: 100 },
  children: (Array.isArray(it) ? it : [{ text: it }]).map(r =>
    new TextRun({ font: r.mono ? MONO : FONT, size: r.size ?? 22,
                  color: r.color ?? INK, ...r })),
}));

const table2 = (head, rows, w = [3000, 6360]) => new Table({
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
        text: t, font: FONT, size: 21, bold: true, color: INK })] })],
    })) }),
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

const numbering = [
  { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET,
    text: "•", style: { paragraph: { indent: { left: 420, hanging: 260 } },
                        run: { color: ACCENT } } }] },
];

// ------------------------------------------------------------------ content
const children = [];

children.push(
  p("SAIL — DURGAPUR STEEL PLANT", { size: 20, color: MUTE, after: 60 }),
  new Paragraph({ spacing: { after: 80 }, children: [new TextRun({
    text: "DSP Commodity Intelligence", font: FONT, size: 52, bold: true,
    color: ACCENT })] }),
  p("Intelligent Commodity Price Prediction & Procurement Decision Engine",
    { size: 26, color: INK, after: 40 }),
  p("Deployment & Operations Guide", { size: 24, bold: true, after: 40 }),
  p("Pravartanam · SAIL Digital Transformation Division · August 2026",
    { size: 20, color: MUTE, after: 320 }),
  new Paragraph({
    spacing: { after: 300 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 10, color: ACCENT } },
    children: [new TextRun({ text: " ", size: 2 })],
  }),
  p("This guide takes the packaged application from a zip file on your laptop to a live, shareable dashboard on Streamlit Community Cloud, and covers the monthly data-refresh routine, alternative hosting options, and troubleshooting. Total time for a first deployment: about 30 minutes, most of it waiting for the first cloud build.",
    { size: 22, after: 200 }),
  new Paragraph({ children: [new TextRun({ text: "Contents", font: FONT, size: 25, bold: true, color: INK })], spacing: { before: 120, after: 140 } }),
  ...[
    "1. What you are deploying",
    "2. Prerequisites",
    "3. Step 1 — Verify locally (10 minutes)",
    "4. Step 2 — Push to a private GitHub repository",
    "5. Step 3 — Deploy on Streamlit Community Cloud",
    "6. Refreshing data — upload, merge, audit",
    "7. Alternative hosting (when to outgrow the free tier)",
    "8. Troubleshooting",
    "9. Security & data notes",
    "10. Two-minute health check (any time)",
  ].map(t => new Paragraph({ spacing: { after: 70 }, indent: { left: 240 },
        children: [new TextRun({ text: t, font: FONT, size: 21, color: INK })] })),
  new Paragraph({ children: [new PageBreak()] }),
);

// 1 overview
children.push(
  h1("1. What you are deploying"),
  p("The application is a single Streamlit app backed by pre-computed model artifacts. All heavy work — data cleaning, the 19-model bake-off across 102 commodities, champion selection, forecast generation — happens offline in the training script. The dashboard itself only reads artifacts and runs the light interactive mathematics (fuzzy verdicts, negotiation bands, inventory dials), so it starts fast and stays responsive on the free cloud tier."),
  p("Flow of information:", { bold: true, after: 100 }),
  code([
    "SAP PO export (.xlsx)",
    "   └─► python -m src.train_all        (offline, ~20 min, checkpointed)",
    "          └─► data/processed/*        (prices, forecasts, champions, signals)",
    "                 └─► streamlit run app.py   (reads artifacts, never retrains on load)",
  ]),
  p("Because artifacts are committed to the repository, the cloud app works immediately after deployment with no build-time training and no secrets."),

  h2("1.1 Package inventory"),
  table2(["Path", "Purpose"], [
    [[{ text: "app.py", mono: true }], "The dashboard — nine pages, from the Command Center and Impact Tracker to the Admin upload flow."],
    [[{ text: "src/", mono: true }], "Pipeline, model zoo, ensembles, walk-forward referee, decision engine, external-data fetcher."],
    [[{ text: "data/raw/", mono: true }], "The PO workbook. Replace this file for every refresh."],
    [[{ text: "data/processed/", mono: true }], "Trained artifacts: monthly prices, catalog, leaderboard, champions, forecasts, decision signals, quarantine audit."],
    [[{ text: "data/audit/", mono: true }], "Upload audit trail (append-only JSONL) and byte-for-byte archive of every accepted upload."],
    [[{ text: "notebooks/01_model_laboratory.ipynb", mono: true }], "Executed audit trail of the whole modelling story, with real outputs."],
    [[{ text: "smoke_test.py", mono: true }], "One-command verification that every dashboard code path works."],
    [[{ text: "requirements.txt", mono: true }], "Exact dependency set for cloud and local installs."],
    [[{ text: ".streamlit/config.toml", mono: true }], "The control-room theme."],
    [[{ text: "docs/", mono: true }], "This guide."],
  ]),
);

// 2 prerequisites
children.push(
  h1("2. Prerequisites"),
  ...bullets([
    [{ text: "A GitHub account", bold: true }, { text: " (free). The repository must be " }, { text: "private", bold: true }, { text: " — it contains real procurement data. Streamlit's free tier deploys one private app, which is exactly what you need." }],
    [{ text: "A Streamlit Community Cloud account", bold: true }, { text: " (free) — sign in at share.streamlit.io with the same GitHub account." }],
    [{ text: "Python 3.11 or 3.12 locally", bold: true }, { text: " with pip, for the verification run and future retraining. (3.10 also works.)" }],
    [{ text: "Git installed locally", bold: true }, { text: ", or GitHub Desktop if you prefer clicks to commands." }],
  ]),
);

// 3 local verify
children.push(
  h1("3. Step 1 — Verify locally (10 minutes)"),
  p("Always run the app once on your own machine before pushing. This proves the package is intact and shows you the dashboard exactly as the cloud will render it."),
  ...numberedList([
    [{ text: "Unzip the package to a working folder, e.g. " }, { text: "D:\\dsp-commodity-intelligence", mono: true }, { text: " or " }, { text: "~/dsp-commodity-intelligence", mono: true }, { text: "." }],
    [{ text: "Open a terminal in that folder and create a clean environment:" }],
  ], "s3"),
  code([
    "python -m venv .venv",
    "# Windows:  .venv\\Scripts\\activate      |  Linux/macOS:  source .venv/bin/activate",
    "pip install -r requirements.txt",
  ]),
  ...numberedList([
    [{ text: "Run the smoke test — it exercises every function the dashboard calls:" }],
  ], "s3"),
  code(["python smoke_test.py", "# expect:  All checks passed — the dashboard is safe to launch."]),
  ...numberedList([
    [{ text: "Launch the app and click through all eight pages:" }],
  ], "s3"),
  code(["streamlit run app.py", "# opens http://localhost:8501"]),
  p("The Market Pulse page will fetch external indices live on this first run and cache them under data/external_cache/ — with internet available you should see several series load with a 'live (Yahoo / World Bank / ECB)' status.", { italics: true, color: MUTE }),
);

// 4 github
children.push(
  h1("4. Step 2 — Push to a private GitHub repository"),
  ...numberedList([
    [{ text: "On github.com choose " }, { text: "New repository", bold: true }, { text: ", name it (e.g. " }, { text: "dsp-commodity-intelligence", mono: true }, { text: "), set visibility to " }, { text: "Private", bold: true }, { text: ", and create it empty (no README — the package has one)." }],
    [{ text: "From your working folder, initialise and push:" }],
  ]),
  code([
    "git init",
    "git add .",
    "git commit -m \"DSP Commodity Intelligence — initial deployment\"",
    "git branch -M main",
    "git remote add origin https://github.com/<your-user>/dsp-commodity-intelligence.git",
    "git push -u origin main",
  ]),
  p("The whole repository is under 15 MB (raw workbook ~2 MB, artifacts ~8 MB), far inside GitHub's limits, so committing the processed artifacts is deliberate: it is what lets the cloud app start without training."),
);

// 5 streamlit cloud
children.push(
  h1("5. Step 3 — Deploy on Streamlit Community Cloud"),
  ...numberedList([
    [{ text: "Go to " }, { text: "share.streamlit.io", mono: true }, { text: " and sign in with GitHub. Authorise Streamlit to access your private repositories when prompted." }],
    [{ text: "Click " }, { text: "Create app → Deploy a public app from GitHub", bold: true }, { text: " (the wording covers private repos too once authorised)." }],
    [{ text: "Repository: " }, { text: "<your-user>/dsp-commodity-intelligence", mono: true }, { text: "  ·  Branch: " }, { text: "main", mono: true }, { text: "  ·  Main file path: " }, { text: "app.py", mono: true }, { text: "." }],
    [{ text: "Optionally set a friendly URL such as " }, { text: "dsp-commodity-intel", mono: true }, { text: ", then click " }, { text: "Deploy", bold: true }, { text: "." }],
    [{ text: "First build takes 3–6 minutes (dependency install). Watch the log panel; when it settles, the Command Center appears." }],
    [{ text: "Open Market Pulse once — the cloud machine fetches and caches the external indices. No API keys are required anywhere; the FRED endpoint is keyless." }],
    [{ text: "Share the app: the URL works for anyone you give it to. To restrict access, use the app's " }, { text: "Settings → Sharing", bold: true }, { text: " panel and invite viewers by email (viewers sign in with Google/GitHub; the repository itself stays private)." }],
  ]),
  p("Free-tier behaviour worth knowing: the app sleeps after ~12 hours without visitors and wakes on the next visit (~1 minute); resources are 1 GB RAM, which this app fits comfortably because it only reads artifacts.", { italics: true, color: MUTE }),
);

// 6 refresh
children.push(
  h1("6. Refreshing data — upload, merge, audit"),
  p("Refreshing is now a self-service action inside the portal itself. Anyone you authorise can do it; no terminal needed for the routine case."),
  h2("6.1 The in-app flow (recommended)"),
  ...numberedList([
    [{ text: "Open " }, { text: "Admin — Data & Retraining", bold: true }, { text: " in the sidebar and enter your name (and a remark like 'monthly refresh')." }],
    [{ text: "Drag & drop the latest SAP export onto the upload box — same MAIN SHEET layout, full dump or partial extract, either works." }],
    [{ text: "Watch the five stages run: archive & backup → merge → price rebuild → model refresh for affected commodities only → decision signals. A typical monthly file finishes in a few minutes because only what changed gets re-refereed." }],
    [{ text: "That's it — every page reflects the new data immediately, the audit trail records the upload, and the Impact Tracker snapshots the fresh signals so they can be verified against reality in later uploads." }],
  ], "s6"),
  h2("6.2 What the merge actually does"),
  ...bullets([
    [{ text: "New PO lines are added", bold: true }, { text: "; lines SAP has revised since the last export (a delivery booked, so Quantity Received grew) are " }, { text: "updated", bold: true }, { text: "; and history the file doesn't mention is " }, { text: "kept untouched", bold: true }, { text: " — a partial extract can never erase the past." }],
    [{ text: "Re-uploading a file that's already applied changes nothing: the portal recognises its fingerprint and says so. Safe against double-clicks and duplicate emails." }],
    [{ text: "Every accepted upload is archived byte-for-byte, the previous master is backed up beside the new one, and rejected files are logged too — the audit trail records who, when, what changed, how long it took, and the file's SHA-256." }],
  ]),
  h2("6.3 Making it permanent on Streamlit Cloud"),
  p("A cloud upload is live for every user immediately, but the cloud filesystem resets on reboot. After uploading there, use the two download buttons (refreshed master workbook + audit CSV), drop them into your local clone, and push:"),
  code(["git add data/", "git commit -m \"Data refresh: <month>\"", "git push   # Streamlit Cloud redeploys automatically"]),
  p("Alternatively, do the upload on a locally-run copy of the app (streamlit run app.py) and push from there — identical result. On a plant-network installation this step doesn't exist: the disk is permanent.", { italics: true, color: MUTE }),
  h2("6.4 Command-line route (still available)"),
  code(["python -m src.train_all --refresh   # full rebuild, ~20 min, checkpointed", "python smoke_test.py"]),
);

// 7 alternatives
children.push(
  h1("7. Alternative hosting (when to outgrow the free tier)"),
  table2(["Option", "When it fits, and how"], [
    ["Streamlit Community Cloud (recommended start)", "Zero cost, zero servers, auto-redeploy on push, private-repo support. Fine for a coordination-level tool with tens of users."],
    ["Hugging Face Spaces (Streamlit SDK)", "Also free, slightly more RAM headroom, same push-to-deploy feel. Create a private Space, choose the Streamlit SDK, push this repo to it unchanged."],
    ["Plant network / on-premises", [{ text: "Where data policy requires everything inside SAIL's network: any Windows/Linux box with Python runs " }, { text: "streamlit run app.py --server.port 8501", mono: true }, { text: " behind the plant LAN. Register it as a scheduled task or systemd service for always-on." }]],
    ["Docker (any server or cloud VM)", [{ text: "One file, one command: a python:3.12-slim image, " }, { text: "pip install -r requirements.txt", mono: true }, { text: ", entry " }, { text: "streamlit run app.py --server.address 0.0.0.0", mono: true }, { text: ". Suits IT-managed hosting with a reverse proxy." }]],
  ], [2700, 6660]),
  p("Suggested path: launch on Community Cloud today; if usage grows or policy tightens, move to the plant network — the codebase needs no changes for any of these options."),
);

// 8 troubleshooting
children.push(
  h1("8. Troubleshooting"),
  table2(["Symptom", "Fix"], [
    [["'Model artifacts not found' banner"], [{ text: "The app cannot see data/processed/. Ensure the folder was committed and pushed (check it on github.com), or run " }, { text: "python -m src.train_all", mono: true }, { text: " locally." }]],
    [["Cloud build fails on dependencies"], [{ text: "Confirm requirements.txt is at the repository root and unmodified. In the app's cloud settings, pick Python 3.12, then " }, { text: "Reboot app", mono: true }, { text: "." }]],
    [["Market Pulse shows 'unavailable' for every series"], "The host had no outbound internet at fetch time, or FRED was briefly down. The panel auto-retries every 6 hours; a cached copy keeps serving once any fetch has succeeded. It will never invent numbers."],
    [["App feels slow after a data push"], "First load after redeploy rebuilds Streamlit's cache (~20–30 s). Subsequent loads are instant."],
    [["Retrain interrupted midway"], [{ text: "By design it checkpoints per commodity. Just rerun " }, { text: "python -m src.train_all", mono: true }, { text: " — it resumes where it stopped." }]],
    [["Upload rejected in the Admin page"], "The file's columns don't match the SAP layout — the error lists exactly which are missing. Nothing was changed; fix the export and re-drop it. The rejection itself is recorded in the audit trail."],
    [["Upload says 'already applied'"], "The portal fingerprints every file (SHA-256). This exact file was merged before — see the audit trail for when and by whom. Re-uploading is intentionally a no-op."],
    [["A new export changes column names"], [{ text: "Keep the MAIN SHEET headers identical to the original (Material Code, Material Description, PR Number, PO No, PO Date, Quantity Received, PO Rel Date, Total PO Value, PO Group, PR Est Value, PR Qty., Ordering Mode). The pipeline validates against these names." }]],
  ], [3100, 6260]),
);

// 9 security
children.push(
  h1("9. Security & data notes"),
  ...bullets([
    "Keep the repository private. It contains genuine procurement prices, quantities and tender modes.",
    "No credentials exist anywhere in the codebase — the external-data endpoint is keyless, so there are no secrets to rotate or leak.",
    "The dashboard is read-only over the data except for the clearly-labelled Admin page; nothing a viewer clicks can alter the committed artifacts.",
    "For wider rollout under SAIL IT policy, prefer the plant-network option in section 7 and put the app behind the intranet.",
  ]),
  h1("10. Two-minute health check (any time)"),
  code(["python smoke_test.py"]),
  p("If it prints 'All checks passed', every page of the dashboard is guaranteed to have what it needs. Make it a habit after each refresh, before each push."),
  new Paragraph({
    spacing: { before: 360 },
    border: { top: { style: BorderStyle.SINGLE, size: 8, color: "D8D8D8" } },
    children: [new TextRun({
      text: "DSP Commodity Intelligence · SDTD, Pravartanam · Prepared August 2026",
      font: FONT, size: 18, color: MUTE })],
  }),
);

const doc = new Document({
  numbering: { config: numbering },
  features: { updateFields: true },
  styles: { default: { document: { run: { font: FONT, size: 22, color: INK } } } },
  sections: [{
    properties: { page: { margin: {
      top: convertInchesToTwip(0.9), bottom: convertInchesToTwip(0.9),
      left: convertInchesToTwip(1.0), right: convertInchesToTwip(1.0) } } },
    children,
  }],
});

Packer.toBuffer(doc).then(b => {
  fs.writeFileSync("docs/DSP_Commodity_Intelligence_Deployment_Guide.docx", b);
  console.log("docx written:", b.length, "bytes");
});
