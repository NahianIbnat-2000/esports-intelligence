"""Rebuild the League of Legends analytical dataset end to end.

Usage (from the repository root):

  # preserve manually downloaded files, then rebuild everything
  python -m pipelines.oracle_elixir.run --import ~/Downloads/2024_LoL_esports_match_data_from_OraclesElixir.csv

  # rebuild from files already in data/raw/oracles_elixir/
  python -m pipelines.oracle_elixir.run

  # skip the database load (only produce processed files and reports)
  python -m pipelines.oracle_elixir.run --no-load
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import UTC, datetime

import pandas as pd

from backend.app.database.seed import seed_reference_data
from backend.app.database.session import get_sessionmaker
from backend.app.models import DataIngestionLog, Game
from pipelines.oracle_elixir import clean as clean_mod
from pipelines.oracle_elixir import download, inspect, load, transform, validate
from pipelines.oracle_elixir.config import (INTERMEDIATE_DIR, INTERNATIONAL_LEAGUES, PROCESSED_DIR,
                                            REPORTS_DIR, ensure_dirs)

log = logging.getLogger("pipeline.oracle_elixir")

CLEANING_PROCEDURE = {
    "version": "1.0",
    "unit_of_analysis": "one game (gameid); best-of series are not reconstructed",
    "row_types": "team rows = participantid 100/200 with position 'team'; player rows = participantid 1-10 "
                 "with position top/jng/mid/bot/sup; anything else is excluded and reported",
    "row_exclusions": ["missing gameid", "missing or unparseable date", "missing team name", "result not 0/1",
                       "row type not identifiable", "exact duplicate row",
                       "conflicting duplicate (same gameid+participantid, different values)"],
    "game_validation": ["exactly 2 team rows", "one Blue + one Red", "two different teams",
                        "exactly one winner", "same date on both team rows"],
    "missing_values": "kept as NULL; never converted to zero",
    "team_identity": "source teamid; team name used only when teamid is missing (flagged id_from_name)",
    "tournament": "league + year + split from the source",
}


class StageLogger:
    def __init__(self, sm, run_id: str):
        self.sm, self.run_id = sm, run_id
        self.game_id = None

    def __call__(self, stage: str, status: str, message: str, counts: dict | None = None) -> None:
        getattr(log, "error" if status == "error" else "info")(f"[{stage}] {message}")
        if self.sm is None:
            return
        with self.sm() as db:
            db.add(DataIngestionLog(run_id=self.run_id, game_id=self.game_id, stage=stage, status=status,
                                    message=message, counts=json.loads(json.dumps(counts or {}, default=str))))
            db.commit()


def run(import_paths: list[str] | None = None, url: str | None = None, url_filename: str | None = None,
        do_load: bool = True, database_url: str | None = None) -> dict:
    ensure_dirs()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    sm = get_sessionmaker(database_url) if do_load else None
    stage = StageLogger(sm, run_id)
    if sm is not None:
        with sm() as db:
            seed_reference_data(db)
            stage.game_id = db.query(Game.id).filter(Game.slug == "lol").scalar()

    # 1. acquire
    for p in import_paths or []:
        e = download.import_local_file(p)
        stage("acquire", "ok", f"preserved {e['filename']} sha256={e['sha256'][:12]}")
    if url:
        e = download.download_url(url, url_filename or url.rsplit("/", 1)[-1])
        stage("acquire", "ok", f"downloaded {e['filename']}")
    files = download.registered_files()
    if not files:
        stage("acquire", "error", "no source files in data/raw/oracles_elixir; nothing to process")
        return {"status": "no_data"}

    # 2. inspect + standardise
    frames, per_file_rows, inspections = [], {}, []
    for f in files:
        raw = inspect.read_raw(f["filename"])
        rep = inspect.inspect_frame(raw, f["filename"])
        inspect.write_inspection(rep)
        inspections.append(rep)
        per_file_rows[f["filename"]] = rep["n_rows"]
        if rep["missing_required_columns"]:
            stage("inspect", "error", f"{f['filename']} lacks required columns "
                                      f"{rep['missing_required_columns']}; file skipped")
            continue
        stage("inspect", "ok", f"{f['filename']}: {rep['n_rows']} rows, {rep['n_unique_gameid']} gameids",
              {"absent_expected_columns": rep["expected_columns_absent"]})
        frames.append(clean_mod.standardise(raw, f["filename"]))
    if not frames:
        return {"status": "no_valid_files"}

    # 3. clean
    rows, row_excl, counts = clean_mod.clean(frames)
    rows.to_parquet(INTERMEDIATE_DIR / "clean_rows.parquet", index=False)
    stage("clean", "ok", f"{counts['rows_accepted_after_row_checks']} rows kept, "
                         f"{counts['rows_excluded_row_checks']} excluded", counts)

    # 4. validate games
    status, game_excl = validate.validate_games(rows)
    n_valid = int(status["valid"].sum())
    stage("validate", "ok" if len(game_excl) == 0 else "warning",
          f"{n_valid} valid games, {len(game_excl)} games excluded",
          game_excl["reason"].value_counts().to_dict())

    # 5. transform
    tables = transform.build_tables(rows, status, INTERNATIONAL_LEAGUES)
    for name, df in tables.items():
        df.to_parquet(PROCESSED_DIR / f"{name}.parquet", index=False)
    stage("transform", "ok", f"{len(tables['matches'])} matches, {len(tables['teams'])} teams, "
                             f"{len(tables['players'])} players, {len(tables['tournaments'])} tournaments")

    # exclusions + quality report
    excluded_games_rows = rows[rows["source_game_id"].isin(set(game_excl["source_game_id"]))][
        ["source_file", "source_row", "source_game_id", "participant_id"]].copy()
    excluded_games_rows["reason"] = excluded_games_rows["source_game_id"].map(
        game_excl.set_index("source_game_id")["reason"]).radd("game excluded: ")
    all_excl = pd.concat([row_excl, excluded_games_rows, tables["player_row_exclusions"]], ignore_index=True)
    all_excl.to_csv(REPORTS_DIR / "exclusions.csv", index=False)
    accepted_rows = len(rows) - len(excluded_games_rows) - len(tables["player_row_exclusions"])
    per_file_excl = all_excl.groupby("source_file").size().to_dict()
    counts.update({
        "per_file_rows": per_file_rows,
        "per_file_excluded": {k: int(v) for k, v in per_file_excl.items()},
        "per_file_accepted": {k: int(per_file_rows[k] - per_file_excl.get(k, 0)) for k in per_file_rows},
        "games_valid": n_valid, "games_excluded": int(len(game_excl)),
        "games_excluded_by_reason": game_excl["reason"].value_counts().to_dict(),
        "games_with_incomplete_player_rows": int((~tables["matches"]["player_rows_complete"]).sum()),
        "rows_accepted_final": int(accepted_rows),
        "rows_excluded_total": int(len(all_excl)),
        "validation_status": "passed_with_exclusions" if len(all_excl) else "passed",
    })
    m = tables["matches"]
    quality = {
        "run_id": run_id, "generated_at": datetime.now(UTC).isoformat(), "source": "Oracle's Elixir",
        "files": files, "counts": counts, "cleaning_procedure": CLEANING_PROCEDURE,
        "coverage": {"start": str(m["match_date"].min()), "end": str(m["match_date"].max()),
                     "years": sorted(m["year"].unique().tolist()), "leagues": int(m["league"].nunique())},
        "data_completeness": m["data_completeness"].value_counts(dropna=False).rename(str).to_dict(),
        "inspections": [{k: r[k] for k in ("filename", "n_rows", "n_unique_gameid", "row_types",
                                           "expected_columns_absent")} for r in inspections],
    }
    (REPORTS_DIR / "data_quality_report.json").write_text(json.dumps(quality, indent=2, default=str))

    # 6. load
    if do_load:
        with sm() as db:
            try:
                loaded = load.load(db, tables, files, counts, CLEANING_PROCEDURE)
                db.commit()
            except Exception as exc:  # roll back and record the failure
                db.rollback()
                stage("load", "error", f"load failed and was rolled back: {exc}")
                raise
        stage("load", "ok", "database rebuilt for League of Legends", loaded)
        quality["loaded"] = loaded
    return {"status": "ok", "run_id": run_id, "quality": quality}


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--import", dest="imports", nargs="*", default=[], help="local CSV files to preserve")
    ap.add_argument("--url", help="verified direct download URL")
    ap.add_argument("--url-filename", help="file name to store the URL download under")
    ap.add_argument("--no-load", action="store_true", help="do not write to the database")
    a = ap.parse_args(argv)
    res = run(a.imports, a.url, a.url_filename, do_load=not a.no_load)
    print(json.dumps({k: v for k, v in res.items() if k != "quality"}, indent=2))
    return 0 if res["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
