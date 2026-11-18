"""Column definitions for Oracle's Elixir match data files.

Source layout (documented by the source and checked by inspect.py on every
file): each `gameid` normally has 12 rows: 10 player rows (participantid
1-10) and 2 team summary rows (participantid 100 = Blue, 200 = Red,
position = "team").

Column names have changed across years (for example spaces in "earned gpm"
and "total cs"). Names are normalised by lower-casing and stripping; the
mapping below then renames them to snake_case. Columns absent from a file are
created as NULL and reported in the inspection report, never filled with 0.
"""
from pathlib import Path

from backend.app.core.config import get_settings

SOURCE_KEY = "oracles_elixir"
# DATA_DIR env var overrides the default <repo>/data (used by tests).
DATA_DIR = Path(get_settings().data_dir)
RAW_DIR = DATA_DIR / "raw" / SOURCE_KEY
INTERMEDIATE_DIR = DATA_DIR / "intermediate" / SOURCE_KEY
PROCESSED_DIR = DATA_DIR / "processed" / SOURCE_KEY
REPORTS_DIR = DATA_DIR / "reports"

# Columns without which a row cannot be used at all.
REQUIRED_COLUMNS = ["gameid", "league", "date", "participantid", "side", "position",
                    "teamname", "result"]

# source column (normalised) -> project column
RENAME = {
    "gameid": "source_game_id",
    "datacompleteness": "data_completeness",
    "url": "source_url",
    "league": "league",
    "year": "year",
    "split": "split",
    "playoffs": "playoffs",
    "date": "date",
    "game": "game_in_series",
    "patch": "patch",
    "participantid": "participant_id",
    "side": "side",
    "position": "position",
    "playername": "player_name",
    "playerid": "source_player_id",
    "teamname": "team_name",
    "teamid": "source_team_id",
    "champion": "champion",
    "gamelength": "duration_seconds",
    "result": "result",
    "kills": "kills",
    "deaths": "deaths",
    "assists": "assists",
    "teamkills": "team_kills",
    "teamdeaths": "team_deaths",
    "dragons": "dragons",
    "barons": "barons",
    "towers": "towers",
    "heralds": "heralds",
    "inhibitors": "inhibitors",
    "firstblood": "first_blood",
    "firstdragon": "first_dragon",
    "firstbaron": "first_baron",
    "firsttower": "first_tower",
    "damagetochampions": "damage_to_champions",
    "dpm": "dpm",
    "damageshare": "damage_share",
    "wardsplaced": "wards_placed",
    "controlwardsbought": "control_wards_bought",
    "visionscore": "vision_score",
    "vspm": "vspm",
    "totalgold": "total_gold",
    "earned gpm": "earned_gpm",
    "earnedgoldshare": "gold_share",
    "total cs": "total_cs",
    "cspm": "cspm",
    "golddiffat15": "golddiff_at_15",
    "xpdiffat15": "xpdiff_at_15",
    "csdiffat15": "csdiff_at_15",
}

TEAM_LOL_METRICS = ["dragons", "barons", "towers", "heralds", "inhibitors", "first_blood",
                    "first_dragon", "first_baron", "first_tower", "damage_to_champions", "dpm",
                    "vision_score", "vspm", "total_gold", "earned_gpm", "total_cs", "cspm",
                    "golddiff_at_15", "xpdiff_at_15", "csdiff_at_15"]

PLAYER_LOL_METRICS = ["champion", "damage_to_champions", "dpm", "damage_share", "vision_score",
                      "vspm", "wards_placed", "control_wards_bought", "earned_gpm", "gold_share",
                      "total_cs", "cspm", "golddiff_at_15", "csdiff_at_15"]

PLAYER_POSITIONS = {"top", "jng", "mid", "bot", "sup"}
TEAM_PARTICIPANT_IDS = {100: "Blue", 200: "Red"}

# Leagues treated as tier-1 international events (cross-region, top leagues)
# for the "international" context flag and the regional analysis. Chosen from
# the 2020-2026 files before any model was trained: in each of these events
# every team's main league is a different top-tier league.
#   WLDs = World Championship, MSI = Mid-Season Invitational,
#   FST = First Stand (2025-), EWC = Esports World Cup (2024-).
# Not included: EM/EUM (European Masters, regional), KeSPA Cup (mostly LCK),
# ASI, WSCI and other invitationals whose status was not verified.
INTERNATIONAL_LEAGUES = {"WLDs", "MSI", "FST", "EWC"}


def ensure_dirs() -> None:
    for d in (RAW_DIR, INTERMEDIATE_DIR, PROCESSED_DIR, REPORTS_DIR):
        Path(d).mkdir(parents=True, exist_ok=True)
