"""
Statistical tests for IPL Orange Cap bias analysis.

Tests run:
  A. Chi-square: winner position distribution vs overall batter population
  B. Kruskal-Wallis + Dunn post-hoc: balls faced across position groups
  C. Kruskal-Wallis: powerplay run % across position groups
  D. Wilcoxon signed-rank: actual rank vs normalised rank
  E. Mann-Whitney U: matches played, playoff vs non-playoff teams
  F. Mann-Whitney U: season runs, non-playoff top-5 vs rest of top-5

Results saved to outputs/tables/stats_results.csv
"""

import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
import csv

RAW = Path("data/processed/ball_by_ball.parquet")
REF = Path("data/reference/orange_cap_winners.csv")
OUT = Path("outputs/tables/stats_results.csv")

ALPHA = 0.05


def position_group(avg_pos):
    if avg_pos <= 2:
        return "Opener (1-2)"
    elif avg_pos <= 3:
        return "Top Order (3)"
    elif avg_pos <= 5:
        return "Middle Order (4-5)"
    else:
        return "Finisher (6+)"


def fmt(p):
    if p < 0.001:
        return "p < 0.001"
    return f"p = {p:.4f}"


def sig(p):
    return "YES" if p < ALPHA else "NO"


results = []

print("Loading data...")
bbb = pd.read_parquet(RAW)
bbb = bbb[(bbb["season"] <= 2025) & (bbb["innings"].isin([1, 2]))]

# Legal deliveries exclude wides (batter does not face a wide)
bbb_legal = bbb[bbb["extras_type"] != "wide"]

winners = pd.read_csv(REF)
winners["position_group"] = winners["avg_batting_position"].apply(position_group)

# Batter-season aggregate (balls_faced = legal balls only, excluding wides)
batter_season = (
    bbb_legal.groupby(["season", "batter"])
    .agg(
        balls_faced=("runs_batter", "count"),
        runs=("runs_batter", "sum"),
        avg_pos=("batting_position", "mean"),
        matches=("match_id", "nunique"),
        made_playoffs=("match_stage", lambda x: int((x != "league").any())),
        pp_runs=("runs_batter", lambda x: x[bbb_legal.loc[x.index, "phase"] == "powerplay"].sum()),
        total_runs_for_pp=("runs_batter", "sum"),
    )
    .reset_index()
)
batter_season["position_group"] = batter_season["avg_pos"].apply(position_group)
batter_season["pp_pct"] = batter_season["pp_runs"] / batter_season["total_runs_for_pp"].replace(0, np.nan) * 100

# ── TEST A: Chi-square — winner positions vs population ───────────────────────
print("\n── TEST A: Chi-square (winner positions vs batter population) ──")

# Population position group distribution (min 7 matches to qualify)
pop = batter_season[batter_season["matches"] >= 7]
pop_dist = pop["position_group"].value_counts()

order = ["Opener (1-2)", "Top Order (3)", "Middle Order (4-5)", "Finisher (6+)"]
pop_counts = pd.Series([pop_dist.get(g, 0) for g in order], index=order)
pop_props = pop_counts / pop_counts.sum()

winner_dist = winners["position_group"].value_counts()
winner_counts = pd.Series([winner_dist.get(g, 0) for g in order], index=order)

# Expected winner counts under null (population proportions)
expected = pop_props * winner_counts.sum()

chi2, p_chi2 = stats.chisquare(f_obs=winner_counts.values, f_exp=expected.values)
print(f"  Observed winner counts: {dict(zip(order, winner_counts))}")
print(f"  Expected (null):        {dict(zip(order, expected.round(2)))}")
print(f"  Chi2 = {chi2:.3f}, {fmt(p_chi2)}, significant: {sig(p_chi2)}")

results.append({
    "test": "Chi-square",
    "analysis": "A",
    "question": "Winner position distribution differs from population",
    "statistic": round(chi2, 4),
    "p_value": round(p_chi2, 6),
    "significant": sig(p_chi2),
    "note": f"df=3, n_winners=18, n_pop={pop_counts.sum()}"
})

# ── TEST B: Kruskal-Wallis — balls faced across position groups ───────────────
print("\n── TEST B: Kruskal-Wallis (balls faced by position group) ──")

groups_balls = {g: batter_season[batter_season["position_group"] == g]["balls_faced"].values for g in order}
kw_stat, p_kw = stats.kruskal(*[groups_balls[g] for g in order])
print(f"  H = {kw_stat:.3f}, {fmt(p_kw)}, significant: {sig(p_kw)}")

results.append({
    "test": "Kruskal-Wallis",
    "analysis": "B",
    "question": "Balls faced per season differs across position groups",
    "statistic": round(kw_stat, 4),
    "p_value": round(p_kw, 6),
    "significant": sig(p_kw),
    "note": f"k=4 groups, n={sum(len(v) for v in groups_balls.values())}"
})

# Dunn post-hoc: Opener vs Middle Order (the key comparison)
print("  Post-hoc Dunn (Opener vs Middle Order):")
opener_balls = groups_balls["Opener (1-2)"]
middle_balls = groups_balls["Middle Order (4-5)"]
mw_stat, p_mw = stats.mannwhitneyu(opener_balls, middle_balls, alternative="greater")
print(f"    Mann-Whitney U (Opener > Middle): U = {mw_stat:.0f}, {fmt(p_mw)}, significant: {sig(p_mw)}")
median_diff = np.median(opener_balls) - np.median(middle_balls)
print(f"    Median difference: {median_diff:.1f} balls/season")

results.append({
    "test": "Mann-Whitney U",
    "analysis": "B (post-hoc)",
    "question": "Openers face more balls per season than middle-order",
    "statistic": round(mw_stat, 4),
    "p_value": round(p_mw, 6),
    "significant": sig(p_mw),
    "note": f"one-sided, median diff={median_diff:.1f} balls, n_opener={len(opener_balls)}, n_middle={len(middle_balls)}"
})

# ── TEST C: Kruskal-Wallis — powerplay run % across position groups ───────────
print("\n── TEST C: Kruskal-Wallis (powerplay run % by position group) ──")

bs_valid = batter_season.dropna(subset=["pp_pct"])
groups_pp = {g: bs_valid[bs_valid["position_group"] == g]["pp_pct"].values for g in order}
kw_pp_stat, p_kw_pp = stats.kruskal(*[groups_pp[g] for g in order])
print(f"  H = {kw_pp_stat:.3f}, {fmt(p_kw_pp)}, significant: {sig(p_kw_pp)}")

opener_pp = np.median(groups_pp["Opener (1-2)"])
middle_pp = np.median(groups_pp["Middle Order (4-5)"])
print(f"  Median PP% — Opener: {opener_pp:.1f}%, Middle Order: {middle_pp:.1f}%")

results.append({
    "test": "Kruskal-Wallis",
    "analysis": "C",
    "question": "Powerplay run % differs across position groups",
    "statistic": round(kw_pp_stat, 4),
    "p_value": round(p_kw_pp, 6),
    "significant": sig(p_kw_pp),
    "note": f"k=4 groups, median opener PP%={opener_pp:.1f}, median middle PP%={middle_pp:.1f}"
})

# ── TEST D: Wilcoxon signed-rank — actual rank vs normalised rank ─────────────
print("\n── TEST D: Wilcoxon signed-rank (actual rank vs normalised rank) ──")

# Rebuild league-only batter-season with normalised ranks + confidence intervals
league = bbb[bbb["match_stage"] == "league"]

# Match-level runs needed to compute per-match std dev
match_runs = (
    league.groupby(["season", "batter", "match_id"])["runs_batter"]
    .sum()
    .reset_index()
    .rename(columns={"runs_batter": "match_runs"})
)
league_bs = (
    match_runs.groupby(["season", "batter"])
    .agg(league_matches=("match_id", "nunique"),
         league_runs=("match_runs", "sum"),
         runs_std=("match_runs", "std"))
    .reset_index()
)
avg_pos = league.groupby(["season", "batter"])["batting_position"].mean().reset_index()
avg_pos.columns = ["season", "batter", "avg_pos"]
league_bs = league_bs.merge(avg_pos, on=["season", "batter"])

league_bs = league_bs[league_bs["league_matches"] >= 7]
league_bs["norm_runs"] = league_bs["league_runs"] * 14.0 / league_bs["league_matches"]
league_bs["actual_rank"] = league_bs.groupby("season")["league_runs"].rank(ascending=False, method="min")
league_bs["norm_rank"] = league_bs.groupby("season")["norm_runs"].rank(ascending=False, method="min")

# 95% CI on projected runs for missed matches: ±1.96 × σ × √(missing_matches)
league_bs["missing_matches"] = (14 - league_bs["league_matches"]).clip(lower=0)
league_bs["ci_half"] = 1.96 * league_bs["runs_std"] * np.sqrt(league_bs["missing_matches"])
league_bs["ci_lower"] = (league_bs["norm_runs"] - league_bs["ci_half"]).clip(lower=0).round(1)
league_bs["ci_upper"] = (league_bs["norm_runs"] + league_bs["ci_half"]).round(1)

# Save updated analysis_d CSV
d_out = league_bs[league_bs["actual_rank"] <= 10].copy()
d_out["normalised_runs"] = d_out["norm_runs"].round(1)
d_out["avg_pos"] = d_out["avg_pos"].round(1)
d_out[["season", "batter", "league_matches", "league_runs", "normalised_runs",
       "actual_rank", "norm_rank", "avg_pos", "missing_matches", "ci_lower", "ci_upper"]].sort_values(
    ["season", "actual_rank"]
).to_csv(Path("outputs/tables/analysis_d_normalised_rankings.csv"), index=False)

# Among top-10 actual per season
top10 = league_bs[league_bs["actual_rank"] <= 10]
w_stat, p_w = stats.wilcoxon(top10["actual_rank"], top10["norm_rank"])
rank_shift_pct = (top10["actual_rank"] != top10["norm_rank"]).mean() * 100
print(f"  W = {w_stat:.0f}, {fmt(p_w)}, significant: {sig(p_w)}")
print(f"  {rank_shift_pct:.1f}% of top-10 batters have a different normalised rank")

results.append({
    "test": "Wilcoxon signed-rank",
    "analysis": "D",
    "question": "Actual rank differs from normalised rank (top-10 per season)",
    "statistic": round(w_stat, 4),
    "p_value": round(p_w, 6),
    "significant": sig(p_w),
    "note": f"n={len(top10)}, {rank_shift_pct:.1f}% of rankings shift after normalisation"
})

# ── TEST E: Mann-Whitney U — matches played, playoff vs non-playoff ───────────
print("\n── TEST E: Mann-Whitney U (matches played: playoff vs non-playoff) ──")

team_season = (
    bbb.groupby(["season", "batting_team"])
    .agg(
        matches=("match_id", "nunique"),
        made_playoffs=("match_stage", lambda x: int((x != "league").any()))
    )
    .reset_index()
)
playoff_matches = team_season[team_season["made_playoffs"] == 1]["matches"].values
non_playoff_matches = team_season[team_season["made_playoffs"] == 0]["matches"].values

mw_e_stat, p_mw_e = stats.mannwhitneyu(playoff_matches, non_playoff_matches, alternative="greater")
print(f"  U = {mw_e_stat:.0f}, {fmt(p_mw_e)}, significant: {sig(p_mw_e)}")
print(f"  Median — playoff: {np.median(playoff_matches):.1f}, non-playoff: {np.median(non_playoff_matches):.1f}")

results.append({
    "test": "Mann-Whitney U",
    "analysis": "E",
    "question": "Playoff teams play more matches than non-playoff teams",
    "statistic": round(mw_e_stat, 4),
    "p_value": round(p_mw_e, 6),
    "significant": sig(p_mw_e),
    "note": f"one-sided, n_playoff={len(playoff_matches)}, n_non_playoff={len(non_playoff_matches)}"
})

# ── TEST F: Mann-Whitney U — runs, non-playoff top-5 vs playoff top-5 ─────────
print("\n── TEST F: Mann-Whitney U (season runs: non-playoff top-5 vs playoff top-5) ──")

full_bs = (
    bbb.groupby(["season", "batter"])
    .agg(
        runs=("runs_batter", "sum"),
        matches=("match_id", "nunique"),
        made_playoffs=("match_stage", lambda x: int((x != "league").any()))
    )
    .reset_index()
)
full_bs = full_bs[full_bs["matches"] >= 7]
full_bs["season_rank"] = full_bs.groupby("season")["runs"].rank(ascending=False, method="min")
top5 = full_bs[full_bs["season_rank"] <= 5]

playoff_top5_runs = top5[top5["made_playoffs"] == 1]["runs"].values
non_playoff_top5_runs = top5[top5["made_playoffs"] == 0]["runs"].values

mw_f_stat, p_mw_f = stats.mannwhitneyu(playoff_top5_runs, non_playoff_top5_runs, alternative="greater")
print(f"  U = {mw_f_stat:.0f}, {fmt(p_mw_f)}, significant: {sig(p_mw_f)}")
print(f"  Median runs — playoff top-5: {np.median(playoff_top5_runs):.0f}, non-playoff top-5: {np.median(non_playoff_top5_runs):.0f}")

results.append({
    "test": "Mann-Whitney U",
    "analysis": "F",
    "question": "Playoff top-5 batters score more runs than non-playoff top-5",
    "statistic": round(mw_f_stat, 4),
    "p_value": round(p_mw_f, 6),
    "significant": sig(p_mw_f),
    "note": f"one-sided, n_playoff={len(playoff_top5_runs)}, n_non_playoff={len(non_playoff_top5_runs)}, medians: {np.median(playoff_top5_runs):.0f} vs {np.median(non_playoff_top5_runs):.0f}"
})

# ── Save results ──────────────────────────────────────────────────────────────
df = pd.DataFrame(results)
df.to_csv(OUT, index=False)
print(f"\nResults saved to {OUT}")

print("\n" + "=" * 65)
print("SUMMARY")
print("=" * 65)
print(f"{'Analysis':<10} {'Test':<25} {'Statistic':>12} {'p-value':>12} {'Sig?':>6}")
print(f"{'-'*10} {'-'*25} {'-'*12} {'-'*12} {'-'*6}")
for r in results:
    print(f"  {r['analysis']:<8} {r['test']:<25} {r['statistic']:>12.3f} {r['p_value']:>12.6f} {r['significant']:>6}")
