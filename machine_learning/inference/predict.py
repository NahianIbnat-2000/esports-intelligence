"""Inference: compute pre-game features "as of" a date and apply the saved
models. Pure functions; the backend supplies each team's history.

A team history is a list of earlier games (strictly before `as_of`), oldest
first, each with: date, won (0/1), own rating_after, opponent rating_before.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from machine_learning.elo.elo import expected_score
from machine_learning.feature_engineering.features import FEATURES, WINDOW


@dataclass
class TeamState:
    n_prior: int
    wins_prior: int
    recent: list[int]
    opp_ratings_recent: list[float]
    elo: float
    last_game: datetime | None
    # mean log(1 + earlier pro games) of the players in the team's previous game (pre-match)
    player_exp_prev: float = 0.0


def team_state(history: list[dict], as_of: datetime, elo_cfg: dict) -> TeamState:
    initial = elo_cfg.get("initial", 1500.0)
    if not history:
        return TeamState(0, 0, [], [], initial, None)
    last = history[-1]
    elo = float(last["rating_after"])
    if as_of.year > last["date"].year:  # season carry-over toward the league level, as in training
        level = last.get("league_rating")
        level = initial if level is None else float(level)
        elo = level + (1 - elo_cfg.get("carryover_shrink", 0.0)) * (elo - level)
    recent = history[-WINDOW:]
    return TeamState(n_prior=len(history), wins_prior=int(sum(h["won"] for h in history)),
                     recent=[int(h["won"]) for h in recent],
                     opp_ratings_recent=[float(h["opp_rating_before"]) for h in recent], elo=elo,
                     last_game=last["date"])


def feature_row(blue: TeamState, red: TeamState, international: bool, initial: float = 1500.0) -> dict:
    def rw(s):  # shrunk recent win rate
        return (sum(s.recent) + 1) / (len(s.recent) + 2)

    def hw(s):
        return (s.wins_prior + 2.5) / (s.n_prior + 5)

    def opp(s):
        return float(np.mean(s.opp_ratings_recent)) if s.opp_ratings_recent else initial
    elo_diff = blue.elo - red.elo
    return {"elo_diff": elo_diff, "recent_wr_diff": rw(blue) - rw(red), "hist_wr_diff": hw(blue) - hw(red),
            "opp_strength_diff": opp(blue) - opp(red),
            "experience_diff": float(np.log1p(blue.n_prior) - np.log1p(red.n_prior)),
            "elo_diff_x_intl": elo_diff * float(international),
            "player_exp_prev_diff": blue.player_exp_prev - red.player_exp_prev}


def p_blue(model_key: str, feats: dict, models: dict) -> float:
    if model_key == "elo":
        return float(expected_score(feats["_blue_elo"], feats["_red_elo"]))
    if model_key == "logreg_player":
        cols = FEATURES + ["player_exp_prev_diff"]
        return float(models["logreg_player"].predict_proba(pd.DataFrame([{k: feats[k] for k in cols}]))[:, 1][0])
    X = pd.DataFrame([{k: feats[k] for k in FEATURES}])
    if model_key == "elo_logit":
        return float(models["elo_logit"].predict_proba(X[["elo_diff"]])[:, 1][0])
    return float(models["logreg"].predict_proba(X[FEATURES])[:, 1][0])


def predict_pair(a: TeamState, b: TeamState, side: str, international: bool, model_key: str, models: dict,
                 initial: float = 1500.0) -> tuple[float, dict]:
    """P(team A wins). side = 'blue' | 'red' | 'unknown' (average of both side assignments)."""
    def with_elos(blue, red):
        f = feature_row(blue, red, international, initial)
        f["_blue_elo"], f["_red_elo"] = blue.elo, red.elo
        return f
    fa = with_elos(a, b)   # A on blue
    fb = with_elos(b, a)   # B on blue
    if side == "blue":
        return p_blue(model_key, fa, models), fa
    if side == "red":
        return 1 - p_blue(model_key, fb, models), fb
    return 0.5 * (p_blue(model_key, fa, models) + 1 - p_blue(model_key, fb, models)), fa
