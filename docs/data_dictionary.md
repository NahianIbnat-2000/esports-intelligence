# Data dictionary

Source column (Oracle's Elixir, lower-cased) → project column. `NULL` = not recorded.

| Source | Project | Level | Definition |
|---|---|---|---|
| gameid | source_match_id | game | Source game id; one game = one match |
| datacompleteness | data_completeness | game | `complete` or `partial` |
| url | source_url | game | Link to the match page when provided |
| league | league | game | League or event code (e.g. LCK, LEC, MSI, WLDs). Competitive region, not a country |
| year, split | tournament | game | Tournament = league + year + split |
| playoffs | playoffs | game | Source playoffs flag |
| date | match_date | game | UTC timestamp |
| game | game_in_series | game | Game number in the series |
| patch | patch | game | Game patch |
| participantid | participant_id | row | 1-10 players, 100 Blue team, 200 Red team |
| side | side | row | Blue / Red |
| position | position | row | top, jng, mid, bot, sup, or team |
| playername / playerid | players.name / source_player_id | player | |
| teamname / teamid | teams.name / source_team_id | team | Name used as id only when teamid is missing (flagged) |
| champion | champion | player | |
| gamelength | duration_seconds | game | Seconds |
| result | result | row | 1 win, 0 loss |
| kills, deaths, assists | same | team/player | Team rows: team totals |
| dragons, barons, towers, heralds, inhibitors | same | team | Objectives taken |
| firstblood, firstdragon, firstbaron, firsttower | first_* | team | 1 if the team got it first |
| damagetochampions | damage_to_champions | team/player | |
| dpm | dpm | team/player | Damage to champions per minute |
| damageshare | damage_share | player | Share of team damage |
| wardsplaced, controlwardsbought | same | player | |
| visionscore, vspm | vision_score, vspm | team/player | Vision score, per minute |
| totalgold | total_gold | team | |
| earned gpm | earned_gpm | team/player | Earned gold per minute |
| earnedgoldshare | gold_share | player | Share of team earned gold |
| total cs, cspm | total_cs, cspm | team/player | Creep score, per minute |
| golddiffat15, xpdiffat15, csdiffat15 | *_at_15 | team/player | Difference at 15:00 vs opponent (team) or lane opponent (player) |

Derived:

| Column | Definition |
|---|---|
| kda | (kills + assists) / deaths; kills + assists when deaths = 0; null if any part is missing |
| teams.primary_league | Most frequent non-international league |
| tournaments.derived_champion | Winner of the chronologically last playoff game |
| teams.current_elo | Elo after the team's last game |
| team_rosters | Observed appearances (not official rosters) |

Player career KDA in the API is computed from totals: (sum kills + sum assists) / max(sum deaths, 1).
