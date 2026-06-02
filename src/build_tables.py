"""
Regenerate analysis output tables from the local parquet + reference CSV.

Produces (in outputs/tables/):
  batter_season.csv                          (7+ match qualifying batter-seasons)
  analysis_a_winner_positions.csv
  analysis_b_balls_faced_by_position.csv
  analysis_c_powerplay_concentration.csv
  analysis_e_playoff_match_advantage.csv
  analysis_f_non_playoff_elite.csv

analysis_d_normalised_rankings.csv and stats_results.csv are produced by stats.py.

Usage:  python src/build_tables.py [MAX_SEASON]   (default MAX_SEASON=2026)

Conventions (match prior pipeline):
  - balls_faced = legal deliveries only (wides excluded; no-balls are faced)
  - avg_pos = delivery-weighted mean of batting_position
  - qualifying threshold = 7+ matches in the season
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

RAW = Path("data/processed/ball_by_ball.parquet")
REF = Path("data/reference/orange_cap_winners.csv")
OUT = Path("outputs/tables")

MAX_SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
MIN_MATCHES = 7
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
    bbb = pd.read_parquet(RAW)
    bbb = bbb[(bbb["season"] <= MAX_SEASON) & (bbb["innings"].isin([1, 2]))]
    bbb_legal = bbb[bbb["extras_type"] != "wide"]

    # ── batter-season aggregate (qualifying: 7+ matches) ──────────────────────
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

    # ── Analysis A: winner positions (reference CSV + position_group) ─────────
    winners = pd.read_csv(REF)
    winners["position_group"] = winners["avg_batting_position"].apply(position_group)
    winners[["season", "winner", "team", "total_runs", "matches_played",
             "avg_batting_position", "position_group", "playoff_team"]].to_csv(
        OUT / "analysis_a_winner_positions.csv", index=False)

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
    # Matches original SQL: over bbb_clean (no 7+ filter), position_group from
    # the batter-season's mean batting_position across all deliveries.
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
    # Matches original SQL: group by (season, batter, batting_team) over
    # bbb_clean, 7+ matches, season_rank by runs, top-5 non-playoff.
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
    f["proj_runs_16_matches"] = round1(f["runs"] / f["matches"] * 16)
    f["avg_pos"] = round1(f["avg_pos"])
    f[["season", "batter", "batting_team", "matches", "runs", "avg_pos",
       "season_rank", "made_playoffs", "runs_per_match", "proj_runs_16_matches"]].astype(
        {"season_rank": int}).sort_values(["season", "season_rank"]).to_csv(
        OUT / "analysis_f_non_playoff_elite.csv", index=False)

    print(f"Tables rebuilt for seasons <= {MAX_SEASON} "
          f"({bs['season'].nunique()} seasons, {len(bs)} qualifying batter-seasons)")


if __name__ == "__main__":
    main()
