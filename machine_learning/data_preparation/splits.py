"""Chronological train / validation / test split.

The split is by game timestamp, never random:
  train      : first 70% of the time-ordered games
  validation : next 15%
  test       : last 15%
Cut dates are taken at game boundaries so no timestamp falls in two splits.

Additional sample rules (applied identically to every model):
- Burn-in: games in the first `burn_in_days` of the data are not used to fit
  or evaluate models, because every Elo rating starts at the same value.
  They are still replayed by Elo so later ratings use them.
- Minimum history: a game is evaluated only if both teams have at least
  `min_prior_games` earlier games.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass
class SplitConfig:
    train_share: float = 0.70
    val_share: float = 0.15
    burn_in_days: int = 90
    min_prior_games: int = 5


def assign_splits(df: pd.DataFrame, cfg: SplitConfig) -> tuple[pd.DataFrame, dict]:
    df = df.sort_values(["match_date", "source_game_id"]).reset_index(drop=True)
    start = df["match_date"].min()
    burn_end = start + pd.Timedelta(days=cfg.burn_in_days)
    eligible = (df["match_date"] >= burn_end) & (df["min_prior_games"] >= cfg.min_prior_games)
    dates = df.loc[eligible, "match_date"]
    if len(dates) == 0:
        df["split"] = "excluded"
        return df, {"error": "no eligible games"}
    train_end = dates.quantile(cfg.train_share)
    val_end = dates.quantile(cfg.train_share + cfg.val_share)
    df["split"] = "excluded"
    df.loc[eligible & (df["match_date"] <= train_end), "split"] = "train"
    df.loc[eligible & (df["match_date"] > train_end) & (df["match_date"] <= val_end), "split"] = "validation"
    df.loc[eligible & (df["match_date"] > val_end), "split"] = "test"
    info = {"config": asdict(cfg), "data_start": str(start), "burn_in_end": str(burn_end),
            "train_end": str(train_end), "validation_end": str(val_end), "data_end": str(df["match_date"].max())}
    for s in ("train", "validation", "test", "excluded"):
        sub = df[df["split"] == s]
        info[s] = {"n": int(len(sub)),
                   "start": str(sub["match_date"].min()) if len(sub) else None,
                   "end": str(sub["match_date"].max()) if len(sub) else None,
                   "blue_win_rate": float(sub["blue_won"].mean()) if len(sub) else None}
    return df, info
