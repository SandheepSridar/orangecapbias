"""TNPL mirror of src/build_tables.py — analysis output tables.

Produces (in TNPL/tables/):
  batter_season.csv                          (4+ match qualifying batter-seasons)
  analysis_a_winner_positions.csv
  analysis_b_balls_faced_by_position.csv
  analysis_c_powerplay_concentration.csv
  analysis_e_playoff_match_advantage.csv
  analysis_f_non_playoff_elite.csv

analysis_d_normalised_rankings.csv and stats_results.csv are produced by stats.py.

Conventions match the IPL pipeline, with thresholds rescaled for TNPL's short
season (7 league matches vs the IPL's 14):
  - qualifying threshold = 4+ matches (IPL: 7+ of 14 — same ~50% bar)
  - balls_faced = legal deliveries only (wides excluded; no-balls are faced)
  - avg_pos = delivery-weighted mean of batting_position
  - Analysis A winner = the season's leading run-scorer (the Most Runs award
    holder; cross-validated against Wikipedia in data_quality_all.py)
  - Analysis F projects to 9 matches (league 7 + 2 playoff, mirroring the
    IPL's 16 = 14 + 2)

Usage:  python3 TNPL/build_tables.py
"""

from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "tnpl_ball_by_ball.csv"
OUT = ROOT / "tables"
OUT.mkdir(exist_ok=True)

MIN_MATCHES = 4
PROJ_MATCHES = 9
POS_ORDER = ["Opener (1-2)", "Top Order (3)", "Middle Order (4-5)", "Finisher (6+)"]


def round1(s):
    """Round to 1 decimal, half-up (matches SQL ROUND, not numpy banker's rounding)."""
    return np.floor(np.asarray(s, dtype=float) * 10 + 0.5) / 10


def position_group(avg_pos):
    if avg_pos <= 2:
        return "Opener (1-2)"
    elif avg_pos <= 3:
        return "Top Order (3)"
    elif avg_pos <= 5:
        return "Middle Order (4-5)"
    return "Finisher (6+)"


def main():
    bbb = pd.read_csv(RAW, keep_default_na=False)
    bbb = bbb[bbb["innings"].isin([1, 2])]
    # deliveries whose striker id is missing in ESPN's feed (older seasons)
    # cannot be attributed to a batter
    bbb = bbb[bbb["batter"] != "UNKNOWN"]
    bbb_legal = bbb[bbb["extras_type"] != "wide"]

    # ── batter-season aggregate (qualifying: 4+ matches) ──────────────────────
    bs = (
        bbb_legal.groupby(["season", "batter"])
        .agg(
            balls_faced=("runs_batter", "count"),
            runs=("runs_batter", "sum"),
            avg_pos=("batting_position", "mean"),
            matches=("match_id", "nunique"),
            made_playoffs=("match_stage", lambda x: int((x != "league").any())),
        )
        .reset_index()
    )
    bs = bs[bs["matches"] >= MIN_MATCHES].copy()
    bs["position_group"] = bs["avg_pos"].apply(position_group)
    bs[["season", "batter", "balls_faced", "runs", "avg_pos",
        "matches", "made_playoffs", "position_group"]].to_csv(
        OUT / "batter_season.csv", index=False)

    # ── Analysis A: Most Runs winner positions (season run leader from data) ──
    full = (
        bbb.groupby(["season", "batter"])
        .agg(
            total_runs=("runs_batter", "sum"),
            matches_played=("match_id", "nunique"),
            avg_batting_position=("batting_position", "mean"),
            made_playoffs=("match_stage", lambda x: int((x != "league").any())),
            team=("batting_team", lambda x: x.mode().iloc[0]),
        )
        .reset_index()
    )
    winners = full.loc[full.groupby("season")["total_runs"].idxmax()].copy()
    winners["position_group"] = winners["avg_batting_position"].apply(position_group)
    winners["avg_batting_position"] = round1(winners["avg_batting_position"])
    winners["playoff_team"] = np.where(winners["made_playoffs"] == 1, "Yes", "No")
    winners = winners.rename(columns={"batter": "winner"})
    winners[["season", "winner", "team", "total_runs", "matches_played",
             "avg_batting_position", "position_group", "playoff_team"]].sort_values(
        "season").to_csv(OUT / "analysis_a_winner_positions.csv", index=False)

    # ── Analysis B: balls faced by position group ────────────────────────────
    b = (
        bs.groupby("position_group")
        .agg(
            batter_seasons=("batter", "count"),
            avg_balls=("balls_faced", "mean"),
            median_balls=("balls_faced", "median"),
            min_balls=("balls_faced", "min"),
            max_balls=("balls_faced", "max"),
            avg_runs=("runs", "mean"),
        )
        .reindex(POS_ORDER)
        .reset_index()
    )
    b["avg_balls"] = b["avg_balls"].round(1)
    b["median_balls"] = b["median_balls"].round(1)
    b["avg_runs"] = b["avg_runs"].round(1)
    b.to_csv(OUT / "analysis_b_balls_faced_by_position.csv", index=False)

    # ── Analysis C: powerplay run concentration ──────────────────────────────
    c_pos = bbb.groupby(["season", "batter"])["batting_position"].mean().reset_index()
    c_pos["position_group"] = c_pos["batting_position"].apply(position_group)
    phase_runs = (
        bbb.groupby(["season", "batter", "phase"], observed=True)["runs_batter"]
        .sum().unstack(fill_value=0).reset_index()
    )
    phase_runs = phase_runs.merge(c_pos[["season", "batter", "position_group"]],
                                  on=["season", "batter"], how="inner")
    c = (
        phase_runs.groupby("position_group")[["powerplay", "middle", "death"]]
        .sum().reindex(POS_ORDER).reset_index()
        .rename(columns={"powerplay": "pp_runs", "middle": "mid_runs", "death": "death_runs"})
    )
    c["total_runs"] = c[["pp_runs", "mid_runs", "death_runs"]].sum(axis=1)
    c["pp_pct"] = round1(c["pp_runs"] / c["total_runs"] * 100)
    c["mid_pct"] = round1(c["mid_runs"] / c["total_runs"] * 100)
    c["death_pct"] = round1(c["death_runs"] / c["total_runs"] * 100)
    c.to_csv(OUT / "analysis_c_powerplay_concentration.csv", index=False)

    # ── Analysis E: matches played per team-season + playoff flag ────────────
    e = (
        bbb.groupby(["season", "batting_team"])
        .agg(
            matches_played=("match_id", "nunique"),
            made_playoffs=("match_stage", lambda x: int((x != "league").any())),
        )
        .reset_index()
        .sort_values(["season", "made_playoffs", "matches_played"],
                     ascending=[True, False, False])
    )
    e.to_csv(OUT / "analysis_e_playoff_match_advantage.csv", index=False)

    # ── Analysis F: non-playoff elite (top-5 season run-scorers) ─────────────
    f = (
        bbb.groupby(["season", "batter", "batting_team"])
        .agg(
            matches=("match_id", "nunique"),
            runs=("runs_batter", "sum"),
            avg_pos=("batting_position", "mean"),
            made_playoffs=("match_stage", lambda x: int((x != "league").any())),
        )
        .reset_index()
    )
    f = f[f["matches"] >= MIN_MATCHES].copy()
    f["season_rank"] = f.groupby("season")["runs"].rank(ascending=False, method="min")
    f = f[(f["season_rank"] <= 5) & (f["made_playoffs"] == 0)].copy()
    f["runs_per_match"] = round1(f["runs"] / f["matches"])
    f[f"proj_runs_{PROJ_MATCHES}_matches"] = round1(f["runs"] / f["matches"] * PROJ_MATCHES)
    f["avg_pos"] = round1(f["avg_pos"])
    f[["season", "batter", "batting_team", "matches", "runs", "avg_pos",
       "season_rank", "made_playoffs", "runs_per_match",
       f"proj_runs_{PROJ_MATCHES}_matches"]].astype(
        {"season_rank": int}).sort_values(["season", "season_rank"]).to_csv(
        OUT / "analysis_f_non_playoff_elite.csv", index=False)

    print(f"Tables rebuilt ({bs['season'].nunique()} seasons, "
          f"{len(bs)} qualifying batter-seasons)")


if __name__ == "__main__":
    main()
