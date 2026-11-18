"""SYNTHETIC test fixture in the Oracle's Elixir row layout.

THIS IS NOT REAL DATA. Team and player names are prefixed with "SYNTH" so
the records can never be mistaken for real results. It is used only by the
automated tests and must never be loaded into a production database.

Layout reproduced from the documented source structure: each gameid has 12
rows = 10 player rows (participantid 1-10, position top/jng/mid/bot/sup)
plus 2 team rows (participantid 100 blue, 200 red, position "team").
The generator also injects known defects so the cleaning pipeline can be
tested: an exact duplicate row, a game missing one team row, a "partial"
game with empty player stats, and a team with no teamid.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

POSITIONS = ["top", "jng", "mid", "bot", "sup"]


def make_fixture(n_teams: int = 8, n_days: int = 400, games_per_day: int = 4, seed: int = 7,
                 league: str = "SYNTH", year_start: int = 2023) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    strength = rng.normal(0, 1, n_teams)
    teams = [(f"oe:team:synth{i:02d}", f"SYNTH Team {i:02d}") for i in range(n_teams)]
    rows = []
    start = datetime(year_start, 1, 15, 10, 0)
    gid = 0
    for d in range(n_days):
        day = start + timedelta(days=d)
        split = "Spring" if day.month <= 6 else "Summer"
        playoffs = int(day.month in (5, 6, 11, 12))
        for g in range(games_per_day):
            a, b = rng.choice(n_teams, 2, replace=False)
            p_blue = 1 / (1 + np.exp(-(strength[a] - strength[b] + 0.1)))
            blue_win = int(rng.random() < p_blue)
            gid += 1
            gameid = f"SYNTH_{gid:06d}"
            ts = day + timedelta(hours=g)
            length = int(rng.integers(1500, 2600))
            partial = gid % 97 == 0
            for side, team_idx, pid_base, res in (("Blue", a, 0, blue_win), ("Red", b, 5, 1 - blue_win)):
                tid, tname = teams[team_idx]
                tkills = int(rng.integers(5, 30))
                tdeaths = int(rng.integers(5, 30))
                for k, pos in enumerate(POSITIONS):
                    kills = int(rng.integers(0, 8))
                    rows.append({
                        "gameid": gameid, "datacompleteness": "partial" if partial else "complete",
                        "url": None, "league": league, "year": ts.year, "split": split,
                        "playoffs": playoffs, "date": ts.strftime("%Y-%m-%d %H:%M:%S"), "game": g % 3 + 1,
                        "patch": "13.1", "participantid": pid_base + k + 1, "side": side, "position": pos,
                        "playername": f"SYNTH Player {team_idx:02d}-{pos}",
                        "playerid": f"oe:player:synth{team_idx:02d}{pos}",
                        "teamname": tname, "teamid": tid, "champion": "SynthChamp",
                        "gamelength": length, "result": res,
                        "kills": kills, "deaths": int(rng.integers(0, 8)), "assists": int(rng.integers(0, 12)),
                        "teamkills": tkills, "teamdeaths": tdeaths,
                        "dpm": np.nan if partial else float(rng.normal(500, 120)),
                        "damageshare": np.nan if partial else 0.2,
                        "damagetochampions": np.nan if partial else float(rng.normal(15000, 3000)),
                        "visionscore": np.nan if partial else float(rng.normal(40, 10)),
                        "vspm": np.nan if partial else float(rng.normal(1.5, 0.4)),
                        "wardsplaced": np.nan if partial else float(rng.integers(5, 40)),
                        "controlwardsbought": np.nan if partial else float(rng.integers(0, 10)),
                        "earned gpm": np.nan if partial else float(rng.normal(250, 50)),
                        "earnedgoldshare": np.nan if partial else 0.2,
                        "total cs": np.nan if partial else float(rng.integers(20, 350)),
                        "cspm": np.nan if partial else float(rng.normal(7, 2)),
                        "golddiffat15": np.nan if partial else float(rng.normal(0, 800)),
                        "csdiffat15": np.nan if partial else float(rng.normal(0, 10)),
                        "xpdiffat15": np.nan if partial else float(rng.normal(0, 600)),
                    })
                rows.append({
                    "gameid": gameid, "datacompleteness": "partial" if partial else "complete", "url": None,
                    "league": league, "year": ts.year, "split": split, "playoffs": playoffs,
                    "date": ts.strftime("%Y-%m-%d %H:%M:%S"), "game": g % 3 + 1, "patch": "13.1",
                    "participantid": 100 if side == "Blue" else 200, "side": side, "position": "team",
                    "playername": None, "playerid": None, "teamname": tname, "teamid": tid,
                    "champion": None, "gamelength": length, "result": res, "kills": tkills,
                    "deaths": tdeaths, "assists": int(rng.integers(10, 60)), "teamkills": tkills,
                    "teamdeaths": tdeaths, "dragons": int(rng.integers(0, 5)), "barons": int(rng.integers(0, 3)),
                    "towers": int(rng.integers(0, 11)), "heralds": int(rng.integers(0, 2)),
                    "inhibitors": int(rng.integers(0, 3)), "firstblood": int(side == "Blue"),
                    "firstdragon": int(side == "Red"), "firstbaron": res, "firsttower": res,
                    "dpm": np.nan if partial else float(rng.normal(2500, 400)),
                    "damagetochampions": np.nan if partial else float(rng.normal(75000, 9000)),
                    "visionscore": np.nan if partial else float(rng.normal(200, 30)),
                    "vspm": np.nan if partial else float(rng.normal(7, 1)),
                    "totalgold": float(rng.normal(55000, 6000)),
                    "earned gpm": np.nan if partial else float(rng.normal(1250, 150)),
                    "total cs": np.nan if partial else float(rng.normal(900, 100)),
                    "cspm": np.nan if partial else float(rng.normal(32, 3)),
                    "golddiffat15": np.nan if partial else float(rng.normal(0, 2000)),
                    "xpdiffat15": np.nan if partial else float(rng.normal(0, 1500)),
                    "csdiffat15": np.nan if partial else float(rng.normal(0, 25)),
                })
    df = pd.DataFrame(rows)
    # Injected defects
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # exact duplicate row
    broken = df["gameid"].iloc[24]
    drop_idx = df[(df["gameid"] == broken) & (df["participantid"] == 200)].index
    df = df.drop(drop_idx)  # game missing its red team row
    no_id = df["teamname"] == "SYNTH Team 07"
    df.loc[no_id, "teamid"] = None  # team without a source id
    return df.reset_index(drop=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--days", type=int, default=400)
    args = ap.parse_args()
    make_fixture(n_days=args.days).to_csv(args.out, index=False)
    print(f"wrote SYNTHETIC fixture to {args.out}")
