"""
Self-service data ingestion for the DSP Commodity Intelligence engine.

Flow: an SAP export (same MAIN SHEET layout) is uploaded through the
dashboard → validated → merged into the master workbook → the pipeline and
the affected models refresh → an append-only audit trail records who
uploaded what, when, and exactly what changed.

Merge semantics (deliberate, and worth understanding):

* The unit of reconciliation is the PO line-group, keyed by
  (PO No, normalised Material Code, PR Number). SAP re-exports the same
  line later with a higher Quantity Received as deliveries book in, and a
  single PO can legitimately carry several lines of one material — so
  row-level matching is unsafe. Group-wise, the uploaded file's version of
  a group **replaces** the stored version (updates), groups present only
  in history are **kept** (a partial extract can never erase the past),
  and groups only in the upload are **added**.
* Re-uploading a file that is already applied changes nothing — the merge
  is idempotent, and the audit trail says so instead of double-counting.

Nothing is destroyed: the previous master is backed up beside the new one,
and every accepted upload is archived byte-for-byte with its SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .data_pipeline import RAW_DEFAULT, _norm_desc

AUDIT_DIR = Path(__file__).resolve().parents[1] / "data" / "audit"
LOG_PATH = AUDIT_DIR / "upload_log.jsonl"
ARCHIVE_DIR = AUDIT_DIR / "archive"

REQUIRED_COLS = ["Material Code", "Material Description", "PR Number",
                 "PO No", "PO Date", "Quantity Received", "PO Rel Date",
                 "Total PO Value", "PO Group", "PR Est Value", "PR Qty.",
                 "Ordering Mode"]
VALUE_COLS = ["PO Date", "Quantity Received", "PO Rel Date",
              "Total PO Value", "PR Est Value", "PR Qty.", "Ordering Mode",
              "Material Description", "PO Group"]


def fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _norm_code(code) -> str:
    s = str(code).strip()
    return s.lstrip("0") or "0"


def _key_frame(df: pd.DataFrame) -> pd.Series:
    po = df["PO No"].astype(str).str.strip()
    mat = df["Material Code"].map(_norm_code)
    pr = pd.to_numeric(df["PR Number"], errors="coerce")
    pr = pr.map(lambda v: "NA" if pd.isna(v) else str(int(v)))
    return po + "|" + mat + "|" + pr


# ------------------------------------------------------------------ validation
def validate_workbook(source) -> dict:
    """source: path or bytes. Returns dict(ok, issues, df, sheet, n_rows, span)."""
    issues: list[str] = []
    try:
        xl = pd.ExcelFile(source)
    except Exception as e:
        return dict(ok=False, issues=[f"File is not a readable Excel workbook ({e})."],
                    df=None, sheet=None, n_rows=0, span=None)
    sheet = "MAIN SHEET" if "MAIN SHEET" in xl.sheet_names else xl.sheet_names[0]
    if sheet != "MAIN SHEET":
        issues.append(f"No 'MAIN SHEET' tab — using first sheet '{sheet}'.")
    df = xl.parse(sheet)
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        return dict(ok=False, df=None, sheet=sheet, n_rows=len(df), span=None,
                    issues=issues + [
                        "Missing required column(s): " + ", ".join(missing),
                        "Expected the standard SAP export layout: "
                        + ", ".join(REQUIRED_COLS)])
    extra = [c for c in df.columns if c not in REQUIRED_COLS]
    if extra:
        issues.append("Ignoring extra column(s): " + ", ".join(extra))
    df = df[REQUIRED_COLS].copy()
    df["PO Date"] = pd.to_datetime(df["PO Date"], errors="coerce")
    bad_dates = int(df["PO Date"].isna().sum())
    if bad_dates:
        issues.append(f"{bad_dates} row(s) have unreadable PO dates — "
                      "they will be skipped.")
        df = df[df["PO Date"].notna()]
    if len(df) == 0:
        return dict(ok=False, issues=issues + ["No usable rows in the file."],
                    df=None, sheet=sheet, n_rows=0, span=None)
    span = (df["PO Date"].min(), df["PO Date"].max())
    return dict(ok=True, issues=issues, df=df, sheet=sheet,
                n_rows=int(len(df)), span=span)


# ----------------------------------------------------------------------- merge
def merge_master(new_df: pd.DataFrame,
                 master_path: str | Path = RAW_DEFAULT,
                 write: bool = True) -> dict:
    """Group-wise reconcile the upload into the master workbook.

    Returns stats: rows added / updated / unchanged, kept-history rows,
    groups touched, changed_commodities (pipeline commodity keys), and the
    resulting totals. With write=True the master is backed up then replaced.
    """
    master_path = Path(master_path)
    old = pd.read_excel(master_path, sheet_name="MAIN SHEET")
    old.columns = [str(c).strip() for c in old.columns]
    old = old[REQUIRED_COLS].copy()
    old["PO Date"] = pd.to_datetime(old["PO Date"], errors="coerce")

    new = new_df[REQUIRED_COLS].copy()
    old["_key"] = _key_frame(old)
    new["_key"] = _key_frame(new)

    old_keys = set(old["_key"])
    new_keys = set(new["_key"])
    added_keys = new_keys - old_keys
    common_keys = new_keys & old_keys
    kept_keys = old_keys - new_keys

    def group_sig(df):
        d = df.copy()
        d["PO Date"] = d["PO Date"].astype("int64")
        d["PO Rel Date"] = pd.to_datetime(
            d["PO Rel Date"], errors="coerce").astype("int64")
        sig = {}
        for k, g in d.groupby("_key"):
            rows = [tuple(r) for r in
                    g[VALUE_COLS[:6]].round(4).fillna(-1).to_numpy()]
            sig[k] = tuple(sorted(map(str, rows)))
        return sig

    common_old = old[old["_key"].isin(common_keys)]
    common_new = new[new["_key"].isin(common_keys)]
    so, sn = group_sig(common_old), group_sig(common_new)
    updated_keys = {k for k in common_keys if so.get(k) != sn.get(k)}
    unchanged_keys = common_keys - updated_keys

    merged = pd.concat([
        old[old["_key"].isin(kept_keys)],
        new,                                   # new version wins for common
    ], ignore_index=True).sort_values(["PO Date", "PO No"]) \
        .reset_index(drop=True)

    touched = new[new["_key"].isin(added_keys | updated_keys)]
    changed_commodities = sorted(
        touched["Material Description"].map(_norm_desc).unique().tolist())

    stats = dict(
        rows_in_upload=int(len(new)),
        rows_added=int(new["_key"].isin(added_keys).sum()),
        rows_updated=int(new["_key"].isin(updated_keys).sum()),
        rows_unchanged=int(new["_key"].isin(unchanged_keys).sum()),
        rows_history_kept=int(old["_key"].isin(kept_keys).sum()),
        groups_added=len(added_keys), groups_updated=len(updated_keys),
        master_rows_before=int(len(old)), master_rows_after=int(len(merged)),
        span_after=[str(merged["PO Date"].min().date()),
                    str(merged["PO Date"].max().date())],
        changed_commodities=changed_commodities,
    )
    if write and (added_keys or updated_keys):
        backup = master_path.with_name(".backup_" + master_path.name)
        shutil.copy2(master_path, backup)
        merged.drop(columns="_key").to_excel(
            master_path, sheet_name="MAIN SHEET", index=False)
        stats["backup"] = str(backup)
    stats["write_applied"] = bool(write and (added_keys or updated_keys))
    return stats


# ----------------------------------------------------------------- audit trail
def already_applied(sha: str, log_path: str | Path = LOG_PATH) -> dict | None:
    log_path = Path(log_path)
    if not log_path.exists():
        return None
    for line in log_path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("sha256") == sha and rec.get("action") == "APPLIED":
            return rec
    return None


def append_audit(record: dict, log_path: str | Path = LOG_PATH) -> None:
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def read_audit(log_path: str | Path = LOG_PATH) -> pd.DataFrame:
    log_path = Path(log_path)
    if not log_path.exists():
        return pd.DataFrame()
    recs = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
    df = pd.DataFrame(recs)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp", ascending=False)
    return df


def archive_upload(data: bytes, filename: str, sha: str,
                   archive_dir: str | Path = ARCHIVE_DIR) -> str:
    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    out = archive_dir / f"{datetime.now():%Y%m%d_%H%M%S}_{sha[:8]}_{safe}"
    out.write_bytes(data)
    return str(out)


# --------------------------------------------------- model artifact invalidation
def invalidate_models(changed: list[str], proc_dir: str | Path) -> dict:
    """Drop bake-off artifacts for changed commodities so the resumable
    trainer re-evaluates exactly those (plus any newly-eligible ones)."""
    proc = Path(proc_dir)
    changed_set = set(changed)
    out = dict(champions_dropped=0, forecast_rows_dropped=0)

    ch = proc / "champions.jsonl"
    if ch.exists():
        lines = [l for l in ch.read_text().splitlines() if l.strip()]
        keep = [l for l in lines
                if json.loads(l).get("commodity") not in changed_set]
        out["champions_dropped"] = len(lines) - len(keep)
        ch.write_text("\n".join(keep) + ("\n" if keep else ""))

    for name, col in (("leaderboard.csv", "commodity"),
                      ("test_predictions.csv", "commodity"),
                      ("forecasts.csv", "commodity")):
        p = proc / name
        if p.exists():
            df = pd.read_csv(p)
            before = len(df)
            df = df[~df[col].isin(changed_set)]
            if name == "forecasts.csv":
                out["forecast_rows_dropped"] = before - len(df)
            df.to_csv(p, index=False)
    return out
