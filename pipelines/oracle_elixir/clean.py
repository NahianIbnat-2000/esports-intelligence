"""Step 3: clean rows (types, row type, duplicates, missing critical fields).

Every removed row is written to an exclusions table with a reason. Nothing is
silently dropped, and missing statistics stay missing (NaN -> NULL).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipelines.oracle_elixir.config import PLAYER_POSITIONS, RENAME, TEAM_PARTICIPANT_IDS

NUMERIC = ["year", "playoffs", "game_in_series", "participant_id", "duration_seconds", "result",
           "kills", "deaths", "assists", "team_kills", "team_deaths", "dragons", "barons", "towers",
           "heralds", "inhibitors", "first_blood", "first_dragon", "first_baron", "first_tower",
           "damage_to_champions", "dpm", "damage_share", "wards_placed", "control_wards_bought",
           "vision_score", "vspm", "total_gold", "earned_gpm", "gold_share", "total_cs", "cspm",
           "golddiff_at_15", "xpdiff_at_15", "csdiff_at_15"]
TEXT = ["source_game_id", "data_completeness", "source_url", "league", "split", "patch", "side",
        "position", "player_name", "source_player_id", "team_name", "source_team_id", "champion"]


def _blank_to_na(s: pd.Series) -> pd.Series:
    s = s.astype("string").str.strip()
    return s.mask(s == "", pd.NA)


def standardise(df: pd.DataFrame, source_file: str) -> pd.DataFrame:
    """Rename to project columns, add absent columns as NULL, coerce types."""
    keep = {c: RENAME[c] for c in df.columns if c in RENAME}
    out = df[list(keep)].rename(columns=keep).copy()
    for col in set(RENAME.values()) - set(out.columns):
        out[col] = np.nan
    for col in TEXT:
        out[col] = _blank_to_na(out[col])
    for col in NUMERIC:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    # Oracle's Elixir dates are UTC timestamps "YYYY-MM-DD HH:MM:SS".
    out["date"] = pd.to_datetime(out["date"], errors="coerce", utc=True)
    out["position"] = out["position"].str.lower()
    out["side"] = out["side"].str.capitalize()
    # Patch numbers are read as floats by some readers (13.1 vs 13.10); keep
    # the text as written in the file.
    out["source_file"] = source_file
    out["source_row"] = np.arange(len(out))
    return out


def classify_rows(df: pd.DataFrame) -> pd.Series:
    """'team', 'player' or 'unknown', using participant id AND position."""
    pid = df["participant_id"]
    is_team = pid.isin(list(TEAM_PARTICIPANT_IDS)) & (df["position"] == "team")
    is_player = pid.between(1, 10) & df["position"].isin(list(PLAYER_POSITIONS))
    return pd.Series(np.select([is_team, is_player], ["team", "player"], "unknown"), index=df.index)


def clean(frames: list[pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return (clean_rows, exclusions, counts)."""
    df = pd.concat(frames, ignore_index=True)
    counts = {"rows_retrieved": int(len(df))}
    df["row_type"] = classify_rows(df)
    excl = []

    def exclude(mask: pd.Series, reason: str) -> None:
        nonlocal df
        if mask.any():
            e = df.loc[mask, ["source_file", "source_row", "source_game_id", "participant_id"]].copy()
            e["reason"] = reason
            excl.append(e)
            df = df.loc[~mask]

    exclude(df["source_game_id"].isna(), "missing gameid")
    exclude(df["date"].isna(), "missing or unparseable date")
    exclude(df["team_name"].isna(), "missing team name")
    exclude(~df["result"].isin([0, 1]), "result not 0/1")
    exclude(df["row_type"] == "unknown", "row type not identifiable (participantid/position)")

    # Duplicates: the same (gameid, participantid) appearing more than once,
    # either inside a file or across overlapping yearly files.
    dup_exact = df.duplicated(subset=[c for c in df.columns if c not in ("source_file", "source_row")],
                              keep="first")
    counts["rows_duplicate_exact"] = int(dup_exact.sum())
    exclude(dup_exact, "exact duplicate row")
    dup_key = df.duplicated(subset=["source_game_id", "participant_id"], keep=False)
    counts["rows_duplicate_conflicting"] = int(dup_key.sum())
    exclude(dup_key, "conflicting duplicate (same gameid+participantid, different values)")

    # Team identity: use the source team id; fall back to the team name and
    # flag it, because names can change or collide.
    df["team_id_from_name"] = df["source_team_id"].isna()
    df["team_key"] = df["source_team_id"].fillna("name:" + df["team_name"])
    df["player_id_from_name"] = df["source_player_id"].isna() & (df["row_type"] == "player")
    df["player_key"] = df["source_player_id"].fillna("name:" + df["player_name"])

    exclusions = pd.concat(excl, ignore_index=True) if excl else pd.DataFrame(
        columns=["source_file", "source_row", "source_game_id", "participant_id", "reason"])
    counts["rows_accepted_after_row_checks"] = int(len(df))
    counts["rows_excluded_row_checks"] = int(len(exclusions))
    return df.reset_index(drop=True), exclusions, counts
