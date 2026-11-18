"""Write training outputs to the database (model versions, Elo history,
validation/test predictions). Replaces previous LoL model outputs."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
from sqlalchemy import delete, insert, select, update

from backend.app.core.jsonutil import jsonable
from backend.app.database.session import get_sessionmaker
from backend.app.models import EloRating, Game, Match, ModelPrediction, ModelVersion, Team
from machine_learning.feature_engineering.features import FEATURE_DEFINITIONS
from pipelines.oracle_elixir.load import records

DISPLAY = {"baseline_50": "Constant 50% (coin flip)",
           "baseline_prevalence": "Constant blue-side win rate (prevalence)",
           "elo": "Elo baseline (with league offsets)", "elo_logit": "Calibrated Elo (logistic on Elo difference)",
           "logreg": "Logistic regression (pre-game features)"}


def persist(out: dict, database_url: str | None = None) -> None:
    r, games = out["result"], out["games"]
    sm = get_sessionmaker(database_url)
    with sm() as db:
        game = db.scalar(select(Game).where(Game.slug == "lol"))
        old = select(ModelVersion.id).where(ModelVersion.game_id == game.id)
        db.execute(delete(ModelPrediction).where(ModelPrediction.model_version_id.in_(old)))
        db.execute(delete(EloRating).where(EloRating.model_version_id.in_(old)))
        db.execute(delete(ModelVersion).where(ModelVersion.game_id == game.id))
        trained = r["status"] == "trained"
        periods = {k: r["split"].get(k) for k in ("train", "validation", "test")}
        periods.update({k: r["split"].get(k) for k in ("train_end", "validation_end", "burn_in_end",
                                                       "data_start", "data_end")})
        mv = {}
        keys = ["elo", "elo_logit", "logreg"] + (["baseline_50", "baseline_prevalence"] if trained else [])
        for key in keys:
            ev = r.get("evaluation", {}).get(key)
            hp = {"elo": {**r["elo_config"], "grid": r["elo_grid"], "league_levels": r.get("league_levels"),
                          "league_offsets": r.get("league_offsets")},
                  "elo_logit": {"elo": r["elo_config"], "regularisation": "none (C=1e6)",
                                **(r.get("elo_logit_parameters") or {})},
                  "logreg": {"elo": r["elo_config"], "C": r.get("best_C"), "C_grid": r.get("C_grid"),
                             "coefficients": r.get("logreg_coefficients"),
                             "intercept": r.get("logreg_intercept"), "feature_means": r.get("feature_means"),
                             "experimental_models": r.get("experimental_models")},
                  "baseline_50": {"probability": 0.5},
                  "baseline_prevalence": r.get("baselines")}[key]
            metrics = None
            if ev:
                metrics = {**ev, "comparisons": {k: v for k, v in r["comparisons"].items()
                                                 if k.startswith(key + "_vs_")},
                           "temporal_breakdown": r["temporal_breakdown"], "league_breakdown": r["league_breakdown"],
                           "class_balance": r["class_balance"]}
            row = ModelVersion(
                game_id=game.id, model_key=key, version=r["version"], display_name=DISPLAY[key],
                status="trained" if trained else "unavailable",
                trained_at=datetime.fromisoformat(r["trained_at"]), periods=jsonable(periods), hyperparameters=jsonable(hp),
                feature_definitions=([] if key.startswith("baseline") else
                                     [f for f in FEATURE_DEFINITIONS if key == "logreg" or f["name"] == "elo_diff"]),
                metrics=jsonable(metrics) if trained else {"reason": r.get("reason")},
                # relative to MODELS_DIR, so the database is portable between machines
                artifact_path=(f"{r['version']}/{key}.joblib" if trained and key != "elo" else None))
            db.add(row)
            db.flush()
            mv[key] = row.id

        match_id = dict(db.execute(select(Match.source_match_id, Match.id).where(Match.game_id == game.id)).all())
        team_id = dict(db.execute(select(Team.source_team_id, Team.id).where(Team.game_id == game.id)).all())
        g = games.copy()
        g["match_id"] = g["source_game_id"].map(match_id)
        g = g[g["match_id"].notna()]
        blue = pd.DataFrame({"model_version_id": mv["elo"], "match_id": g["match_id"].astype(int),
                             "team_id": g["blue_team_key"].map(team_id), "match_date": g["match_date"],
                             "rating_before": g["blue_elo_pre"], "rating_after": g["blue_elo_post"],
                             "league_rating": g["blue_league_post"], "expected_score": g["p_blue_elo"]})
        red = pd.DataFrame({"model_version_id": mv["elo"], "match_id": g["match_id"].astype(int),
                            "team_id": g["red_team_key"].map(team_id), "match_date": g["match_date"],
                            "rating_before": g["red_elo_pre"], "rating_after": g["red_elo_post"],
                            "league_rating": g["red_league_post"], "expected_score": 1 - g["p_blue_elo"]})
        db.execute(insert(EloRating), records(pd.concat([blue, red])))

        # current Elo = rating after each team's last game
        last = pd.concat([blue, red]).sort_values("match_date").groupby("team_id")["rating_after"].last()
        db.execute(update(Team).where(Team.game_id == game.id).values(current_elo=None))
        db.execute(update(Team), [{"id": int(t), "current_elo": float(v)} for t, v in last.items()])

        if trained:
            cols = {"elo": "p_blue_elo", "elo_logit": "p_blue_elo_logit", "logreg": "p_blue_logreg"}
            ev = g[g["split"].isin(["validation", "test"])]
            for key, col in cols.items():
                recs = pd.DataFrame({"model_version_id": mv[key], "match_id": ev["match_id"].astype(int),
                                     "split": ev["split"], "prob_blue_win": ev[col], "blue_won": ev["blue_won"]})
                db.execute(insert(ModelPrediction), records(recs))
        db.commit()
