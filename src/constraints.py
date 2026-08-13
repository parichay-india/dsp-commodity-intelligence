"""
Per-commodity ordering constraints, set by the user in the app:

    moq          minimum ordering quantity a vendor will accept
    max_oq       maximum quantity per single purchase order
    holding_cap  maximum stock the plant can physically hold

Stored as a plain CSV under data/ so it versions with the repository
(commit it after editing on Streamlit Cloud, same as the master workbook).
Blank cells mean "no constraint" — the planner treats them as unbounded.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PATH = Path(__file__).resolve().parents[1] / "data" / "constraints.csv"
COLS = ["commodity", "moq", "max_oq", "holding_cap"]


def load_constraints(path: str | Path = PATH) -> pd.DataFrame:
    p = Path(path)
    if p.exists():
        df = pd.read_csv(p)
        for c in COLS:
            if c not in df.columns:
                df[c] = np.nan
        df = df[COLS]
        for c in COLS[1:]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df
    return pd.DataFrame(columns=COLS)


def constraints_for(com: str, df: pd.DataFrame | None = None,
                    path: str | Path = PATH) -> dict:
    if df is None:
        df = load_constraints(path)
    row = df[df["commodity"] == com]
    if row.empty:
        return dict(moq=np.nan, max_oq=np.nan, holding_cap=np.nan)
    r = row.iloc[0]
    return dict(moq=float(r["moq"]) if np.isfinite(r["moq"]) else np.nan,
                max_oq=float(r["max_oq"]) if np.isfinite(r["max_oq"])
                else np.nan,
                holding_cap=float(r["holding_cap"])
                if np.isfinite(r["holding_cap"]) else np.nan)


def validate(df: pd.DataFrame) -> list[str]:
    """Returns human-readable issues; rows with issues are still saved so
    the user can fix them in place, but the planner ignores inconsistent
    pairs (it uses whichever bounds remain coherent)."""
    issues = []
    for _, r in df.iterrows():
        com = str(r["commodity"])[:36]
        for c in ("moq", "max_oq", "holding_cap"):
            v = r.get(c, np.nan)
            if np.isfinite(v) and v < 0:
                issues.append(f"{com}: {c} is negative")
        if np.isfinite(r.get("moq", np.nan)) and \
                np.isfinite(r.get("max_oq", np.nan)) and \
                r["moq"] > r["max_oq"]:
            issues.append(f"{com}: MOQ ({r['moq']:,.0f}) exceeds max order "
                          f"({r['max_oq']:,.0f})")
        if np.isfinite(r.get("max_oq", np.nan)) and \
                np.isfinite(r.get("holding_cap", np.nan)) and \
                r["max_oq"] > r["holding_cap"]:
            issues.append(f"{com}: max order exceeds holding capacity")
    return issues


def save_constraints(df: pd.DataFrame, path: str | Path = PATH) -> list[str]:
    df = df[COLS].copy()
    for c in COLS[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=COLS[1:], how="all")   # keep only rows with data
    issues = validate(df)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return issues


def stamp(path: str | Path = PATH) -> str:
    p = Path(path)
    return str(p.stat().st_mtime) if p.exists() else "none"
