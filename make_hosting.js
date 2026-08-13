const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  LevelFormat, convertInchesToTwip,
} = require("docx");

const ACCENT = "C0501F", INK = "1A1A1A", MUTE = "5A6470";
const FONT = "Arial", MONO = "Consolas";

const p = (text, o = {}) => new Paragraph({
  spacing: { after: o.after ?? 150 },
  children: [new TextRun({ text, font: FONT, size: o.size ?? 22,
    bold: o.bold, italics: o.italics, color: o.color ?? INK })],
});
const rich = (runs, o = {}) => new Paragraph({
  spacing: { after: o.after ?? 150 },
  children: runs.map(r => (typeof r === "string" ? { text: r } : r))
    .map(r => new TextRun({ font: r.mono ? MONO : FONT,
      size: r.mono ? 20 : (r.size ?? 22), color: r.color ?? INK, ...r })),
});
const h1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1,
  spacing: { before: 340, after: 170 },
  children: [new TextRun({ text: t, font: FONT, size: 28, bold: true, color: ACCENT })] });

let STEP = 0;
const step = (runs) => {
  STEP += 1;
  return new Paragraph({
    spacing: { after: 150 }, indent: { left: 360, hanging: 360 },
    children: [new TextRun({ text: `${STEP}.  `, font: FONT, size: 22,
      bold: true, color: ACCENT }),
      ...(Array.isArray(runs) ? runs : [runs])
        .map(r => (typeof r === "string" ? { text: r } : r))
        .map(r => new TextRun({ font: r.mono ? MONO : FONT,
          size: r.mono ? 20 : 22, color: INK, ...r }))],
  });
};

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
    margins: { top: 130, bottom: 130, left: 210, right: 210 },
    children: lines.map(l => new Paragraph({ spacing: { after: 60 },
      children: (Array.isArray(l) ? l : [l])
        .map(r => (typeof r === "string" ? { text: r } : r))
        .map(r => new TextRun({ font: r.mono ? MONO : FONT,
          size: r.mono ? 19 : 21, color: r.color ?? INK, ...r })) })),
  })] })],
});

const t2 = (head, rows, w = [3000, 6360]) => new Table({
  width: { size: w[0] + w[1], type: WidthType.DXA }, columnWidths: w,
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
    ...rows.map(r => new TableRow({ children: r.map((c, i) => new TableCell({
      width: { size: w[i], type: WidthType.DXA },
      margins: { top: 75, bottom: 75, left: 130, right: 130 },
      children: [new Paragraph({ children:
        (Array.isArray(c) ? c : [c]).map(run =>
          (typeof run === "string" ? { text: run } : run))
          .map(run => new TextRun({ font: run.mono ? MONO : FONT,
            size: run.mono ? 19 : 21, color: INK, ...run })) })] })) })),
  ],
});

const K = [];

K.push(
  p("SAIL — DURGAPUR STEEL PLANT", { size: 20, color: MUTE, after: 60 }),
  new Paragraph({ spacing: { after: 80 }, children: [new TextRun({
    text: "Hosting Guide", font: FONT, size: 50, bold: true, color: ACCENT })] }),
  p("DSP Commodity Intelligence — from zip file to live website, entirely in a web browser",
    { size: 25, after: 40 }),
  p("GitHub web interface → Streamlit Community Cloud · no Git commands, no terminal, no cost",
    { size: 21, color: MUTE, after: 40 }),
  p("Pravartanam · SAIL Digital Transformation Division", { size: 20, color: MUTE, after: 280 }),
  new Paragraph({ spacing: { after: 240 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 10, color: ACCENT } },
    children: [new TextRun({ text: " ", size: 2 })] }),
  p("What you need before starting: the project zip (dsp-commodity-intelligence.zip), a free GitHub account (github.com → Sign up), and about 30 minutes — most of it waiting for the first build. Everything below happens in a browser.", { after: 220 }),
);

K.push(
  h1("Part 1 — Prepare the files on your computer (5 minutes)"),
  step(["Download ", { text: "dsp-commodity-intelligence.zip", mono: true },
    " and extract it (right-click → Extract All on Windows). You get a folder named ",
    { text: "dsp", mono: true }, " containing ", { text: "app.py", mono: true },
    ", ", { text: "requirements.txt", mono: true }, ", and the folders ",
    { text: "src, data, notebooks, docs, .streamlit", mono: true }, "."]),
  step(["One folder needs attention: ", { text: ".streamlit", mono: true },
    " (it holds the theme). Windows shows it normally. On a Mac, press ",
    { text: "Cmd+Shift+.", mono: true },
    " in Finder to reveal hidden items before the upload. If it goes missing, step 10 has the two-minute fix."]),
);

K.push(
  h1("Part 2 — Create the private repository on github.com (3 minutes)"),
  step(["Sign in at github.com, click the ", { text: "+", bold: true },
    " in the top-right corner → ", { text: "New repository", bold: true }, "."]),
  step(["Name it ", { text: "dsp-commodity-intelligence", mono: true },
    ", set visibility to ", { text: "Private", bold: true },
    " (this is real procurement data — do not skip this), tick nothing else (no README, no .gitignore — the package has its own), and click ",
    { text: "Create repository", bold: true }, "."]),
);

K.push(
  h1("Part 3 — Upload everything through the browser (5 minutes)"),
  step(["On the new empty repository page, click the ",
    { text: "uploading an existing file", bold: true },
    " link (later it is Add file → Upload files)."]),
  step(["Open your extracted ", { text: "dsp", mono: true },
    " folder, select EVERYTHING INSIDE IT (Ctrl+A / Cmd+A) — the files and the subfolders — and drag the whole selection onto the upload area. Dragging preserves folder structure. It is roughly 50 files, ~13 MB."]),
  step(["Type a commit message like ", { text: "Initial deployment", mono: true },
    " at the bottom and click ", { text: "Commit changes", bold: true },
    ". Wait for the upload bar to finish before leaving the page."]),
  step(["Verify with this checklist on the repository front page — you must see: ",
    { text: "app.py · requirements.txt · README.md · smoke_test.py", mono: true },
    " and the folders ", { text: "src · data · notebooks · docs · .streamlit", mono: true }, "."]),
  step(["Click into ", { text: "data", mono: true }, " and confirm ",
    { text: "raw", mono: true }, " (the SAP workbook) and ",
    { text: "processed", mono: true },
    " (about nine artifact files) are both present. If processed is missing, the app shows an 'artifacts not found' banner — re-drag the data folder."]),
  step(["If ", { text: ".streamlit", mono: true },
    " did not survive the drag (the Mac hidden-file case): click ",
    { text: "Add file → Create new file", bold: true },
    ", type exactly ", { text: ".streamlit/config.toml", mono: true },
    " as the filename (the slash creates the folder), open the same file from your extracted copy in Notepad/TextEdit, paste its contents in, and commit. Skipping this only loses the custom theme — the app still runs."]),
  callout([[{ text: "The classic mistake: ", bold: true },
    "dragging the dsp FOLDER instead of its CONTENTS nests everything one level deep, and the deploy fails because requirements.txt is not at the repository root. The fix is simply to upload the contents again at the root level."]]),
);

K.push(
  h1("Part 4 — Deploy on Streamlit Community Cloud (10 minutes, mostly waiting)"),
  step(["Go to ", { text: "share.streamlit.io", mono: true },
    ", choose ", { text: "Continue to sign-in → Continue with GitHub", bold: true },
    ", and approve GitHub's authorisation prompts. When asked which repositories Streamlit may access, grant access to this private repository (you can limit it to just this one)."]),
  step(["In your workspace, click ", { text: "Create app", bold: true },
    " (upper-right). When asked whether you already have an app, choose ",
    { text: "Yup, I have an app", bold: true }, "."]),
  step(["Fill the three fields — Repository: ",
    { text: "your-username/dsp-commodity-intelligence", mono: true },
    " · Branch: ", { text: "main", mono: true }, " · Main file path: ",
    { text: "app.py", mono: true },
    ". If the repository is not in the dropdown, the link right there adjusts GitHub permissions — grant access and it appears."]),
  step(["Pick an App URL subdomain, e.g. ", { text: "dsp-commodity-intel", mono: true },
    " → the site becomes ", { text: "dsp-commodity-intel.streamlit.app", mono: true }, "."]),
  step(["Open ", { text: "Advanced settings", bold: true },
    " and confirm the Python version — the default 3.12 is exactly right. Leave Secrets empty; this app needs no keys anywhere. Click ",
    { text: "Deploy", bold: true }, "."]),
  step(["Watch the build log; the first build takes 3–6 minutes while packages install. When it settles, the Command Center appears with all 102 commodities live."]),
  step(["Two first-visit actions: open ", { text: "Market Pulse", bold: true },
    " once so the server fetches and caches the external feeds (expect the Indian indices, World Bank commodities and USD/INR to show 🟢 live), and click through the other pages once to confirm rendering."]),
);

K.push(
  h1("Part 5 — Sharing and access control"),
  step(["The URL works for anyone who has it. To restrict access: open the app menu (⋮, lower-right of the running app, or from the workspace) → ",
    { text: "Settings → Sharing", bold: true },
    " and invite viewers by email. Viewers sign in with Google or GitHub; the repository itself stays private either way."]),
);

K.push(
  h1("Part 6 — The monthly refresh, still browser-only"),
  step(["When the new SAP export arrives, open the deployed app's ",
    { text: "Admin — Data & Retraining", bold: true },
    " page and drag the file in. Validation, safe merge, incremental retraining, signal snapshot and the audit entry all run automatically — the new data is live for every user within minutes."]),
  step(["Make it permanent (the cloud disk resets on reboot): the Admin page offers two download buttons after a successful update — the refreshed master workbook and the audit log. Download both."]),
  step(["On github.com, navigate INTO ", { text: "data/raw", mono: true },
    " → Add file → Upload files → drop the downloaded ",
    { text: "DATA_COMMODITY__PRICING.XLSX", mono: true },
    " (same name replaces the old one) → commit. Repeat inside ",
    { text: "data/audit", mono: true }, " with the audit file."]),
  step(["If you edited ordering constraints (MOQ / max per PO / holding capacity) in the Inventory Planner, download ",
    { text: "constraints.csv", mono: true },
    " from its button there and upload it into ", { text: "data", mono: true },
    " the same way."]),
  step(["Committing triggers an automatic redeploy within a minute or two — the permanent copy and the live app converge, and the loop is closed."]),
);

K.push(
  h1("Part 7 — Troubleshooting"),
  t2(["Symptom", "Cause and fix"], [
    ["Build fails: requirements not found",
     "Files are nested one level deep (the dsp folder was dragged instead of its contents). Upload the contents again at the repository root."],
    ["'Artifacts not found' banner in the app",
     ["The ", { text: "data/processed", mono: true },
      " folder did not upload. Re-drag the data folder from your extracted copy and commit."]],
    ["Repository missing from Streamlit's dropdown",
     "The Streamlit GitHub App lacks access to the private repository. Use the permissions link on the Create-app form, grant access to this repo, refresh."],
    ["App looks unthemed (default colours)",
     [{ text: ".streamlit/config.toml", mono: true },
      " is missing — create it via Part 3, step 10. Cosmetic only."]],
    ["Market Pulse series red on the plant machine",
     "That is the plant network, not the app — the same page on Streamlit Cloud fetches everything. The Test connectivity button names the exact blocker; the proxy field under Advanced network settings accepts the plant proxy address from IT."],
    ["App asleep / slow first visit",
     "The free tier sleeps after ~12 idle hours; the first visitor waits under a minute while it wakes. Normal."],
    ["Forgot whether an upload applied",
     "The Admin page's audit table lists every upload with its fingerprint and outcome (APPLIED / REJECTED / NO_CHANGE). Re-uploading an already-applied file is a recognised no-op."],
  ]),
  new Paragraph({ spacing: { before: 320 },
    border: { top: { style: BorderStyle.SINGLE, size: 8, color: "D8D8D8" } },
    children: [new TextRun({
      text: "DSP Commodity Intelligence · Hosting Guide · companion documents: Deployment Guide (operations detail), Explainer (the Whats and Hows), Project Report (full technical zero-to-hero), prompts.docx (workflow flowcharts).",
      font: FONT, size: 18, color: MUTE })] }),
);

const doc = new Document({
  numbering: { config: [] },
  styles: { default: { document: { run: { font: FONT, size: 22, color: INK } } } },
  sections: [{ properties: { page: { margin: {
    top: convertInchesToTwip(0.9), bottom: convertInchesToTwip(0.9),
    left: convertInchesToTwip(1.0), right: convertInchesToTwip(1.0) } } },
    children: K }],
});

Packer.toBuffer(doc).then(b => {
  fs.writeFileSync("docs/DSP_Hosting_Guide_GitHub_Web_to_Streamlit_Cloud.docx", b);
  console.log("hosting guide written:", b.length, "bytes,", STEP, "steps");
});
