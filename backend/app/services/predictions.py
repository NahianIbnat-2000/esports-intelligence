"""Prediction laboratory: model registry and out-of-sample predictions."""
from __future__ import annotations

from datetime import UTC, datetime, time
from functools import lru_cache
from pathlib import Path

import joblib
from fastapi import HTTPException
from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session, aliased

from backend.app.core.config import get_settings
from backend.app.models import EloRating, Game, Match, ModelPrediction, ModelVersion, Team, TeamMatchStatistic, Tournament
from backend.app.schemas.common import ModelProbability, PredictionRequest, PredictionResponse
from machine_learning.inference.predict import predict_pair, team_state

MIN_PRIOR_GAMES = 5
CAVEATS = [
    "Probabilities describe uncertainty; they do not guarantee any outcome.",
    "Inputs use only games recorded before the prediction date. Roster changes, patches, and draft are not "
    "modelled.",
    "Models predict a single game, not a best-of series.",
    "Ratings stop changing after the last game in the data; predictions for later dates use frozen ratings.",
]


def model_versions(db: Session, game: Game) -> list[ModelVersion]:
    return list(db.scalars(select(ModelVersion).where(ModelVersion.game_id == game.id).order_by(ModelVersion.id)))


def models_payload(db: Session, game: Game) -> list[dict]:
    out = []
    for m in model_versions(db, game):
        out.append({"model_key": m.model_key, "display_name": m.display_name, "version": m.version,
                    "status": m.status, "trained_at": m.trained_at, "periods": m.periods,
                    "hyperparameters": m.hyperparameters, "feature_definitions": m.feature_definitions,
                    "metrics": m.metrics})
    return out


@lru_cache(maxsize=8)
def _load_artifact(path: str, mtime: float):
    return joblib.load(path)


def _artifact(path: str | None):
    """Artifacts are stored as paths relative to MODELS_DIR, so the same
    database works on any machine that has the artifact files."""
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = Path(get_settings().models_dir) / p
    elif not p.exists():  # absolute path from another machine: try the local models dir
        p = Path(get_settings().models_dir) / p.parent.name / p.name
    if not p.exists():
        return None
    return _load_artifact(str(p), p.stat().st_mtime)


def _history(db: Session, elo_mv: ModelVersion, team_id: int, before: datetime) -> list[dict]:
    Opp = aliased(EloRating)
    rows = db.execute(
        select(Match.match_date, TeamMatchStatistic.result, EloRating.rating_after, Opp.rating_before,
               EloRating.league_rating)
        .join(TeamMatchStatistic, TeamMatchStatistic.match_id == Match.id)
        .join(EloRating, and_(EloRating.match_id == Match.id, EloRating.team_id == team_id,
                              EloRating.model_version_id == elo_mv.id))
        .join(Opp, and_(Opp.match_id == Match.id, Opp.team_id == TeamMatchStatistic.opponent_team_id,
                        Opp.model_version_id == elo_mv.id))
        .where(TeamMatchStatistic.team_id == team_id, Match.match_date < before)
        .order_by(Match.match_date, Match.id)).all()
    return [{"date": d, "won": int(r), "rating_after": ra, "opp_rating_before": ob, "league_rating": lr}
            for d, r, ra, ob, lr in rows]


def predict(db: Session, game: Game, req: PredictionRequest) -> PredictionResponse:
    if game.status == "integration_pending":
        raise HTTPException(409, f"Predictions are unavailable for {game.name}: provider integration pending.")
    if req.team_a == req.team_b:
        raise HTTPException(422, "Choose two different teams.")
    mvs = {m.model_key: m for m in model_versions(db, game)}
    elo_mv = mvs.get("elo")
    if elo_mv is None or elo_mv.status != "trained":
        reason = (elo_mv.metrics or {}).get("reason") if elo_mv else "No model has been trained yet."
        raise HTTPException(409, f"Predictions are currently unavailable: {reason}")
    teams = {t.slug: t for t in db.scalars(select(Team).where(Team.game_id == game.id,
                                                              Team.slug.in_([req.team_a, req.team_b])))}
    for s in (req.team_a, req.team_b):
        if s not in teams:
            raise HTTPException(404, f"team '{s}' not found")
    as_of = datetime.combine(req.as_of, time.min, tzinfo=UTC)
    val_end = datetime.fromisoformat(elo_mv.periods["validation_end"])
    if as_of <= val_end:
        raise HTTPException(422, f"Out-of-sample predictions are only available for dates after "
                                 f"{val_end.date()} (end of the validation period). Earlier dates were used to "
                                 f"choose or fit the models.")
    ta, tb = teams[req.team_a], teams[req.team_b]
    elo_cfg = {k: elo_mv.hyperparameters[k] for k in ("initial", "carryover_shrink", "k")}
    sa = team_state(_history(db, elo_mv, ta.id, as_of), as_of, elo_cfg)
    sb = team_state(_history(db, elo_mv, tb.id, as_of), as_of, elo_cfg)
    for t, s in ((ta, sa), (tb, sb)):
        if s.n_prior < MIN_PRIOR_GAMES:
            raise HTTPException(422, f"{t.name} has {s.n_prior} recorded games before {req.as_of}; at least "
                                     f"{MIN_PRIOR_GAMES} are needed (the same rule used in evaluation).")
    models = {"elo_logit": _artifact(mvs["elo_logit"].artifact_path) if "elo_logit" in mvs else None,
              "logreg": _artifact(mvs["logreg"].artifact_path) if "logreg" in mvs else None}
    preds, feats = [], None
    for key in ("elo", "elo_logit", "logreg"):
        mv = mvs.get(key)
        if mv is None or mv.status != "trained" or (key != "elo" and models.get(key) is None):
            preds.append(ModelProbability(model_key=key, display_name=mv.display_name if mv else key,
                                          version=mv.version if mv else "-", status="unavailable",
                                          prob_team_a=None, prob_team_b=None,
                                          reason="model artifact missing or model not trained"))
            continue
        p, f = predict_pair(sa, sb, req.team_a_side, req.context == "international", key, models,
                            elo_cfg["initial"])
        feats = feats or f
        preds.append(ModelProbability(model_key=key, display_name=mv.display_name, version=mv.version,
                                      status="trained", prob_team_a=p, prob_team_b=1 - p))
    explanation = _explain(db, game, mvs, models.get("logreg"), feats, ta, tb, as_of, sa, sb, req, preds)
    caveats = list(CAVEATS)
    data_end = datetime.fromisoformat(elo_mv.periods["data_end"])
    if as_of > data_end:
        caveats.insert(0, f"The prediction date is after the last game in the data ({data_end.date()}).")

    def info(t, s):
        return {"slug": t.slug, "name": t.name, "elo": s.elo, "games_before": s.n_prior,
                "wins_before": s.wins_prior, "last_game": s.last_game, "recent_results": s.recent}
    return PredictionResponse(
        team_a=info(ta, sa), team_b=info(tb, sb), as_of=req.as_of, team_a_side=req.team_a_side, context=req.context,
        predictions=preds,
        inputs={"features_team_a_on_blue": {k: v for k, v in (feats or {}).items() if not k.startswith("_")},
                "feature_note": "Differences are blue minus red with team A on the blue side. With side "
                                "'unknown' the probability is the average of both side assignments."},
        generated_at=datetime.now(UTC), caveats=caveats, explanation=explanation)


def _explain(db, game, mvs, logreg, feats, ta, tb, as_of, sa, sb, req, preds) -> dict:
    """Why the models predict what they predict. Every number comes from the
    stored model or from games before `as_of`."""
    import numpy as np

    from machine_learning.feature_engineering.features import FEATURES
    Blue, Red = aliased(Team), aliased(Team)
    h2h = db.execute(select(Match.winner_team_id, Match.match_date)
                     .where(Match.game_id == game.id, Match.match_date < as_of,
                            ((Match.blue_team_id == ta.id) & (Match.red_team_id == tb.id))
                            | ((Match.blue_team_id == tb.id) & (Match.red_team_id == ta.id)))
                     .order_by(desc(Match.match_date))).all()
    wins_a = sum(1 for w, _ in h2h if w == ta.id)
    out: dict = {
        "elo_difference_a_minus_b": sa.elo - sb.elo,
        "recent_form": {"team_a": {"games": len(sa.recent), "wins": sum(sa.recent)},
                        "team_b": {"games": len(sb.recent), "wins": sum(sb.recent)}},
        "head_to_head_before_date": {"games": len(h2h), "wins_a": wins_a, "wins_b": len(h2h) - wins_a,
                                     "last_meeting": h2h[0][1] if h2h else None,
                                     "note": "Shown for context only; head-to-head is not a model input."},
        "side_advantage": None, "logreg_contributions": None, "summary": [],
    }
    el = mvs.get("elo_logit")
    if el and el.hyperparameters and "implied_blue_win_prob_equal_elo" in el.hyperparameters:
        out["side_advantage"] = {
            "blue_win_prob_equal_teams": el.hyperparameters["implied_blue_win_prob_equal_elo"],
            "applied": req.team_a_side,
            "note": "Estimated by the calibrated Elo model (intercept). With side 'unknown' both side "
                    "assignments are averaged, so the side effect cancels out."}
    if logreg is not None and feats:
        scaler, lr = logreg.named_steps["scale"], logreg.named_steps["lr"]
        x = np.array([feats[f] for f in FEATURES])
        z = (x - scaler.mean_) / scaler.scale_
        contrib = lr.coef_[0] * z
        logit = float(lr.intercept_[0] + contrib.sum())
        out["logreg_contributions"] = {
            "orientation": "team A on the blue side",
            "intercept": float(lr.intercept_[0]),
            "features": sorted([{"feature": f, "value": float(v), "standardised": float(zz),
                                 "contribution_log_odds": float(c)}
                                for f, v, zz, c in zip(FEATURES, x, z, contrib)],
                               key=lambda r: -abs(r["contribution_log_odds"])),
            "logit": logit, "probability_team_a_on_blue": float(1 / (1 + np.exp(-logit))),
            "note": "Contribution = coefficient x standardised feature value, in log-odds relative to an "
                    "average game. Contributions plus the intercept add up to the model's logit.",
        }
        top = out["logreg_contributions"]["features"][:2]
        for r in top:
            direction = "towards team A" if r["contribution_log_odds"] > 0 else "towards team B"
            out["summary"].append(f"{r['feature']} pushes the logistic prediction {direction} "
                                  f"({r['contribution_log_odds']:+.2f} log-odds).")
    d = sa.elo - sb.elo
    out["summary"].insert(0, f"Team A's rating is {abs(d):.0f} Elo points {'above' if d >= 0 else 'below'} team B's "
                             f"before {req.as_of}; on its own that gives team A "
                             f"{next((p.prob_team_a for p in preds if p.model_key == 'elo'), float('nan')):.0%} "
                             "under the Elo model.")
    return out


def history(db: Session, game: Game, team: str | None, league: str | None, date_from, date_to, split: str | None,
            page: int, page_size: int) -> tuple[list[dict], int, dict]:
    """Stored out-of-sample predictions (validation and test periods) with
    outcomes and model versions, plus monthly Brier scores for the selection."""
    from sqlalchemy import func
    mvs = {m.model_key: m for m in model_versions(db, game)
           if m.status == "trained" and not m.model_key.startswith("baseline")}
    if "elo" not in mvs:
        return [], 0, {}
    Blue, Red = aliased(Team), aliased(Team)
    q = (select(Match.id, Match.match_date, Tournament.name, Tournament.league, Blue.name, Blue.slug, Red.name,
                Red.slug, ModelPrediction.blue_won, ModelPrediction.split)
         .join(ModelPrediction, and_(ModelPrediction.match_id == Match.id,
                                     ModelPrediction.model_version_id == mvs["elo"].id))
         .join(Tournament, Tournament.id == Match.tournament_id)
         .join(Blue, Blue.id == Match.blue_team_id).join(Red, Red.id == Match.red_team_id))
    if team:
        q = q.where((Blue.slug == team) | (Red.slug == team))
    if league:
        q = q.where(Tournament.league == league)
    if date_from:
        q = q.where(Match.match_date >= date_from)
    if date_to:
        q = q.where(Match.match_date <= date_to)
    if split:
        q = q.where(ModelPrediction.split == split)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(desc(Match.match_date)).offset((page - 1) * page_size).limit(page_size)).all()
    ids = [r[0] for r in rows]
    probs: dict = {}
    for key, mv in mvs.items():
        for mid, p in db.execute(select(ModelPrediction.match_id, ModelPrediction.prob_blue_win)
                                 .where(ModelPrediction.model_version_id == mv.id, ModelPrediction.match_id.in_(ids))):
            probs.setdefault(mid, {})[key] = p
    out = [{"match_id": r[0], "date": r[1], "tournament": r[2], "league": r[3], "blue_team": r[4],
            "blue_team_slug": r[5], "red_team": r[6], "red_team_slug": r[7], "blue_won": r[8], "split": r[9],
            "prob_blue_win": probs.get(r[0], {})} for r in rows]
    # monthly Brier for the whole selection (not only this page)
    sub = q.with_only_columns(Match.id.label("mid"), Match.match_date.label("d")).subquery()
    month = func.date_trunc("month", sub.c.d) if db.bind.dialect.name == "postgresql" \
        else func.strftime("%Y-%m-01", sub.c.d)
    monthly: dict = {}
    for key, mv in mvs.items():
        for mth, n, b in db.execute(
                select(month, func.count(), func.avg((ModelPrediction.prob_blue_win - ModelPrediction.blue_won)
                                                     * (ModelPrediction.prob_blue_win - ModelPrediction.blue_won)))
                .join(ModelPrediction, ModelPrediction.match_id == sub.c.mid)
                .where(ModelPrediction.model_version_id == mv.id).group_by(month).order_by(month)):
            monthly.setdefault(str(mth)[:7], {"month": str(mth)[:7], "n": int(n)})[f"{key}_brier"] = float(b)
    meta = {"versions": {k: v.version for k, v in mvs.items()},
            "monthly": [v for v in monthly.values() if v["n"] >= 20],
            "note": "Validation-period predictions come from models fitted on the training period; test-period "
                    "predictions from models fitted on training + validation. Every input is from games before "
                    "the predicted game."}
    return out, total, meta


def test_predictions(db: Session, game: Game, team: str | None, limit: int) -> list[dict]:
    """Stored out-of-sample (test period) predictions with actual outcomes."""
    mvs = {m.model_key: m for m in model_versions(db, game) if m.status == "trained"}
    if not mvs:
        return []
    Blue, Red = aliased(Team), aliased(Team)
    q = (select(Match.id, Match.match_date, Tournament.name, Blue.name, Blue.slug, Red.name, Red.slug,
                ModelPrediction.blue_won)
         .join(ModelPrediction, and_(ModelPrediction.match_id == Match.id,
                                     ModelPrediction.model_version_id == mvs["elo"].id, ModelPrediction.split == "test"))
         .join(Tournament, Tournament.id == Match.tournament_id)
         .join(Blue, Blue.id == Match.blue_team_id).join(Red, Red.id == Match.red_team_id))
    if team:
        q = q.where((Blue.slug == team) | (Red.slug == team))
    rows = db.execute(q.order_by(desc(Match.match_date)).limit(limit)).all()
    ids = [r[0] for r in rows]
    probs = {}
    for key, mv in mvs.items():
        for mid, p in db.execute(select(ModelPrediction.match_id, ModelPrediction.prob_blue_win)
                                 .where(ModelPrediction.model_version_id == mv.id, ModelPrediction.match_id.in_(ids))):
            probs.setdefault(mid, {})[key] = p
    return [{"match_id": r[0], "date": r[1], "tournament": r[2], "blue_team": r[3], "blue_team_slug": r[4],
             "red_team": r[5], "red_team_slug": r[6], "blue_won": r[7], "prob_blue_win": probs.get(r[0], {})}
            for r in rows]
