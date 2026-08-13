"""Build TNPL/website/data_2026.js — provisional, in-progress-season MOVI data.

Separate from build_data.py (which covers the 9 complete 2016-2025 seasons)
because 2026 is still being played: `tnpl_ball_by_ball.csv` already carries
its rows (prepare_data.py auto-discovers tnpl_2026_bbb.csv), but folding a
partial season into the main site's history would misrepresent it as
comparable to a complete one. This script filters to season 2026 only and
computes the same v1 MOVI methodology (mirrors middle_order_index.py) so the
2026 page can show a live, clearly-labelled "provisional" leaderboard that
gets replaced by the real thing once the season concludes and joins the main
tables/ pipeline.

Run from the repo root: python3 TNPL/website/build_data_2026.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent  # TNPL/
OUT = Path(__file__).resolve().parent / "data_2026.js"
SEASON = 2026
MIN_MATCHES = 4

bbb = pd.read_csv(ROOT / "tnpl_ball_by_ball.csv", keep_default_na=False)
bbb = bbb[(bbb["season"] == SEASON) & (bbb["innings"].isin([1, 2])) & (bbb["batter"] != "UNKNOWN")]
legal = bbb[bbb["extras_type"] != "wide"]

matches_played = bbb["match_id"].nunique()
matches = pd.read_csv(ROOT / "tnpl_2026_matches.csv", keep_default_na=False)
matches_total = len(matches)

agg = bbb.groupby("batter").agg(
    runs=("runs_batter", "sum"),
    avg_pos=("batting_position", "mean"),
    matches=("match_id", "nunique"),
    team=("batting_team", lambda x: x.mode().iloc[0]),
).reset_index()
balls = legal.groupby("batter")["runs_batter"].count().rename("balls").reset_index()
agg = agg.merge(balls, on="batter", how="left")
agg["balls"] = agg["balls"].fillna(0).astype(int)

inns = bbb.groupby(["batter", "match_id"])["runs_batter"].sum().reset_index()
inns_stats = inns.groupby("batter")["runs_batter"].agg(
    mean_rpi="mean", median_rpi="median", innings="count").reset_index()
agg = agg.merge(inns_stats, on="batter")

death = legal[legal["phase"] == "death"]
death_stats = death.groupby("batter").agg(
    death_runs=("runs_batter", "sum"), death_balls=("runs_batter", "count")).reset_index()
agg = agg.merge(death_stats, on="batter", how="left")
agg["death_balls"] = agg["death_balls"].fillna(0)
agg["death_runs"] = agg["death_runs"].fillna(0)

agg = agg[agg["balls"] > 0].copy()
agg["sr"] = agg["runs"] / agg["balls"] * 100
agg["death_sr"] = np.where(agg["death_balls"] > 0, agg["death_runs"] / agg["death_balls"] * 100, np.nan)

comp = agg[(agg["avg_pos"] >= 3.75) & (agg["avg_pos"] <= 7)].copy()
comp_cols = ["batter", "team", "avg_pos", "matches", "innings", "runs",
             "mean_rpi", "median_rpi", "sr", "death_sr"]
comp = comp[comp_cols].round(
    {"avg_pos": 3, "mean_rpi": 4, "median_rpi": 4, "sr": 4, "death_sr": 4})
comp_rows = [[None if pd.isna(v) else v for v in row] for row in comp.itertuples(index=False)]

# current season run-leader (provisional — will change as more matches are played)
leader = agg.loc[agg["runs"].idxmax()]
leader_row = [leader["batter"], int(leader["runs"]), round(leader["runs"] / leader["balls"] * 100, 1)]

payload = (
    "const MOVI_DATA_2026 = {\n"
    f"  season: {SEASON},\n"
    f"  matchesPlayed: {matches_played},\n"
    f"  matchesTotal: {matches_total},\n"
    f"  compCols: {json.dumps(comp_cols)},\n"
    f"  comp: {json.dumps(comp_rows)},\n"
    "  // [batter, runs, strike rate] of the current provisional run-leader\n"
    f"  runsLeader: {json.dumps(leader_row)},\n"
    f"  minMatches: {MIN_MATCHES}\n"
    "};\n"
)
OUT.write_text(payload)
print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB, {len(comp_rows)} component rows, "
      f"{matches_played}/{matches_total} matches played)")
