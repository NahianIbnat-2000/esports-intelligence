"""Step 2: inspect each raw file before cleaning.

Writes data/reports/inspection/<file>.json with: row count, columns and
types, missing share per column, row-type counts, years, leagues, and which
expected columns are absent. Cleaning is driven by what this finds rather
than by assumptions about every year having the same columns.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipelines.oracle_elixir.config import RAW_DIR, RENAME, REPORTS_DIR, REQUIRED_COLUMNS


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def read_raw(filename: str) -> pd.DataFrame:
    return normalise_columns(pd.read_csv(RAW_DIR / filename, low_memory=False))


def inspect_frame(df: pd.DataFrame, filename: str) -> dict:
    cols = list(df.columns)
    pid = pd.to_numeric(df.get("participantid"), errors="coerce") if "participantid" in df else None
    report = {
        "filename": filename,
        "n_rows": int(len(df)),
        "n_columns": len(cols),
        "columns": {c: {"dtype": str(df[c].dtype), "missing_share": round(float(df[c].isna().mean()), 4)}
                    for c in cols},
        "missing_required_columns": [c for c in REQUIRED_COLUMNS if c not in cols],
        "expected_columns_absent": [c for c in RENAME if c not in cols],
        "unmapped_columns": [c for c in cols if c not in RENAME],
        "n_unique_gameid": int(df["gameid"].nunique()) if "gameid" in df else None,
        "row_types": None,
        "years": sorted(pd.to_numeric(df["year"], errors="coerce").dropna().astype(int).unique().tolist())
        if "year" in df else None,
        "leagues": df["league"].value_counts().to_dict() if "league" in df else None,
        "data_completeness": df["datacompleteness"].value_counts(dropna=False).astype(int)
        .rename(lambda x: str(x)).to_dict() if "datacompleteness" in df else None,
    }
    if pid is not None:
        report["row_types"] = {
            "team_rows (participantid 100/200)": int(pid.isin([100, 200]).sum()),
            "player_rows (participantid 1-10)": int(pid.between(1, 10).sum()),
            "other": int((~pid.isin([100, 200]) & ~pid.between(1, 10)).sum()),
        }
    return report


def write_inspection(report: dict) -> Path:
    out = REPORTS_DIR / "inspection"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{Path(report['filename']).stem}.json"
    path.write_text(json.dumps(report, indent=2, default=str))
    return path
