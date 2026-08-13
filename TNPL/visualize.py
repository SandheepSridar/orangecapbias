"""TNPL mirror of src/visualize.py — publication-quality figures.

fig1–fig6 mirror the IPL Orange Cap bias figures (the TNPL equivalent of the
Orange Cap is the Most Runs award). fig7 adds the MOVI strike-rate dumbbell
(run leader vs best middle-order batsman per season).

Outputs PNG (300 DPI) and SVG to TNPL/figures/.
Run after build_tables.py, stats.py and middle_order_index.py.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import stats as scipy_stats

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT   = Path(__file__).resolve().parent
BASE   = ROOT / "tables"
OUTDIR = ROOT / "figures"
OUTDIR.mkdir(parents=True, exist_ok=True)

YEARS = "2016–2025"

# ── Palette ───────────────────────────────────────────────────────────────────
POS_ORDER  = ["Opener (1-2)", "Top Order (3)", "Middle Order (4-5)", "Finisher (6+)"]
POS_COLORS = {
    "Opener (1-2)":       "#e07b39",
    "Top Order (3)":      "#f5c518",
    "Middle Order (4-5)": "#3a86ff",
    "Finisher (6+)":      "#8ecae6",
}
PHASE_COLORS = ["#e07b39", "#3a86ff", "#6c757d"]

# ── Global style ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    "figure.dpi":        150,
    "savefig.dpi":       300,
    "font.family":       "sans-serif",
    "font.size":         11,
    "axes.titlesize":    13,
    "axes.labelsize":    11,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "grid.color":        "#e0e0e0",
    "grid.linewidth":    0.7,
    "legend.frameon":    False,
})


def save(fig, name):
    fig.savefig(OUTDIR / f"{name}.png", bbox_inches="tight")
    fig.savefig(OUTDIR / f"{name}.svg", bbox_inches="tight")
    print(f"  Saved {name}.png / .svg")
    plt.close(fig)


# ── Load data ─────────────────────────────────────────────────────────────────
a   = pd.read_csv(BASE / "analysis_a_winner_positions.csv")
c   = pd.read_csv(BASE / "analysis_c_powerplay_concentration.csv")
d   = pd.read_csv(BASE / "analysis_d_normalised_rankings.csv")
e   = pd.read_csv(BASE / "analysis_e_playoff_match_advantage.csv")
bs  = pd.read_csv(BASE / "batter_season.csv")
moi = pd.read_csv(BASE / "middle_order_index_best.csv")

n_seasons = a["season"].nunique()


# ── Figure 1 — Most Runs award winner positions ───────────────────────────────
print("Figure 1: Winner positions...")
fig, ax = plt.subplots(figsize=(7, 4.5))

counts = a["position_group"].value_counts().reindex(POS_ORDER, fill_value=0)
colors = [POS_COLORS[g] for g in POS_ORDER]
bars = ax.bar(POS_ORDER, counts.values, color=colors, width=0.55, zorder=3)

for bar, val in zip(bars, counts.values):
    if val > 0:
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.1,
                str(val), ha="center", va="bottom", fontweight="bold", fontsize=12)

ax.set_xlabel("Batting Position Group")
ax.set_ylabel("Number of Most Runs Award Winners")
ax.set_title(f"TNPL Most Runs Award Winners by Batting Position ({YEARS})", pad=12)
ax.set_ylim(0, n_seasons + 1)
ax.set_yticks(range(0, n_seasons + 2, 2))
ax.tick_params(axis="x", length=0)
ax.grid(axis="x", visible=False)

mid_fin = counts["Middle Order (4-5)"] + counts["Finisher (6+)"]
if mid_fin == 0:
    ax.annotate(f"Zero middle-order\nor finisher winners\nin {n_seasons} seasons",
                xy=(2.5, 0.3), fontsize=9, color="#555",
                ha="center", style="italic")

fig.tight_layout()
save(fig, "fig1_winner_positions")


# ── Figure 2 — Balls faced by position group (box plot) ──────────────────────
print("Figure 2: Balls faced...")
fig, ax = plt.subplots(figsize=(7, 4.5))

data_by_group = [bs[bs["position_group"] == g]["balls_faced"].values for g in POS_ORDER]
bp = ax.boxplot(data_by_group, patch_artist=True, notch=False,
                medianprops=dict(color="white", linewidth=2.5),
                whiskerprops=dict(linewidth=1.2),
                capprops=dict(linewidth=1.2),
                flierprops=dict(marker="o", markersize=3, alpha=0.4, linestyle="none"))

for patch, g in zip(bp["boxes"], POS_ORDER):
    patch.set_facecolor(POS_COLORS[g])
    patch.set_alpha(0.85)

medians = [np.median(g) for g in data_by_group]
for i, (med, grp) in enumerate(zip(medians, POS_ORDER), start=1):
    ax.text(i + 0.32, med, f"  {med:.0f}", va="center", fontsize=9.5, color="#333")

ax.set_xticklabels(POS_ORDER)
ax.set_xlabel("Batting Position Group")
ax.set_ylabel("Balls Faced per Season")
ax.set_title("TNPL: Balls Faced per Season by Batting Position Group", pad=12)
ax.tick_params(axis="x", length=0)
ax.grid(axis="x", visible=False)

opener_med  = medians[0]
middle_med  = medians[2]
ax.annotate("",
            xy=(1, opener_med), xytext=(1, middle_med),
            arrowprops=dict(arrowstyle="<->", color="#e07b39", lw=1.8),
            xycoords=("axes fraction", "data"), textcoords=("axes fraction", "data"))
ax.text(1.02, (opener_med + middle_med) / 2,
        f"+{opener_med - middle_med:.0f} balls",
        transform=ax.get_yaxis_transform(), va="center", fontsize=9,
        color="#e07b39", fontweight="bold")

fig.tight_layout()
save(fig, "fig2_balls_faced")


# ── Figure 3 — Powerplay run concentration (stacked bar) ─────────────────────
print("Figure 3: Powerplay concentration...")
fig, ax = plt.subplots(figsize=(7, 4.5))

c_plot = c.set_index("position_group").reindex(POS_ORDER)
phases = ["pp_pct", "mid_pct", "death_pct"]
labels = ["Powerplay (Ov 1–6)", "Middle (Ov 7–15)", "Death (Ov 16–20)"]
bottom = np.zeros(len(POS_ORDER))

for pct_col, label, color in zip(phases, labels, PHASE_COLORS):
    vals = c_plot[pct_col].values
    bars = ax.bar(POS_ORDER, vals, bottom=bottom, color=color,
                  label=label, width=0.55, zorder=3)
    for bar, val, bot in zip(bars, vals, bottom):
        if val > 4:
            ax.text(bar.get_x() + bar.get_width() / 2, bot + val / 2,
                    f"{val:.1f}%", ha="center", va="center",
                    fontsize=9, color="white", fontweight="bold")
    bottom += vals

ax.set_xlabel("Batting Position Group")
ax.set_ylabel("Share of Season Runs (%)")
ax.set_title("TNPL: Run Distribution by Phase and Batting Position Group", pad=12)
ax.set_ylim(0, 108)
ax.legend(loc="upper right", fontsize=9)
ax.tick_params(axis="x", length=0)
ax.grid(axis="x", visible=False)

fig.tight_layout()
save(fig, "fig3_powerplay_concentration")


# ── Figure 4 — Season runs vs average batting position (scatter) ──────────────
print("Figure 4: Runs vs batting position scatter...")
fig, ax = plt.subplots(figsize=(7.5, 5))

for grp in POS_ORDER:
    sub = bs[bs["position_group"] == grp]
    ax.scatter(sub["avg_pos"], sub["runs"],
               color=POS_COLORS[grp], alpha=0.45, s=18, linewidths=0, label=grp)

slope, intercept, r, p, _ = scipy_stats.linregress(bs["avg_pos"], bs["runs"])
x_line = np.linspace(bs["avg_pos"].min(), bs["avg_pos"].max(), 100)
ax.plot(x_line, intercept + slope * x_line,
        color="#333", linewidth=1.8, linestyle="--", zorder=5, label="Trend line")

ax.set_xlabel("Average Batting Position")
ax.set_ylabel("Season Runs")
ax.set_title(f"TNPL: Season Runs vs. Average Batting Position ({YEARS})", pad=12)
ax.legend(fontsize=9, markerscale=1.5, loc="upper right")

p_label = "p < 0.001" if p < 0.001 else f"p = {p:.4f}"
ax.text(0.03, 0.08, f"r = {r:.2f},  {p_label}",
        transform=ax.transAxes, ha="left", va="bottom",
        fontsize=9.5, color="#333",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#ccc"))

fig.tight_layout()
save(fig, "fig4_runs_vs_position")


# ── Figure 5 — Normalised vs actual rankings (dot plot) ──────────────────────
print("Figure 5: Normalised rankings...")
fig, ax = plt.subplots(figsize=(5.5, 5.5))

top10 = d[d["actual_rank"] <= 10].copy()
jitter = np.random.default_rng(42).uniform(-0.15, 0.15, len(top10))

changed = top10["actual_rank"] != top10["norm_rank"]
ax.scatter(top10.loc[~changed, "actual_rank"] + jitter[~changed.values],
           top10.loc[~changed, "norm_rank"],
           color="#adb5bd", alpha=0.5, s=22, linewidths=0, label="Rank unchanged")
ax.scatter(top10.loc[changed, "actual_rank"] + jitter[changed.values],
           top10.loc[changed, "norm_rank"],
           color="#e07b39", alpha=0.65, s=22, linewidths=0, label="Rank changed")

ax.plot([1, 10], [1, 10], color="#555", linewidth=1.2,
        linestyle="--", zorder=2, label="No change (diagonal)")

ax.set_xlabel("Actual Rank")
ax.set_ylabel("Normalised Rank (league-length baseline)")
ax.set_title("TNPL: Actual vs. Normalised Rankings\n(Top-10 batters, all seasons)", pad=12)
ax.set_xticks(range(1, 11))
ax.legend(fontsize=9, loc="upper left")

shift_pct = changed.mean() * 100
ax.text(0.97, 0.97, f"{shift_pct:.1f}% of top-10 batters\nhave a different\nnormalised rank",
        transform=ax.transAxes, ha="right", va="top", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fff7f0", edgecolor="#e07b39"))

fig.tight_layout()
save(fig, "fig5_normalised_rankings")


# ── Figure 6 — Match count: playoff vs non-playoff ───────────────────────────
print("Figure 6: Match count advantage...")
fig, ax = plt.subplots(figsize=(6, 4.5))

playoff     = e[e["made_playoffs"] == 1]["matches_played"].values
non_playoff = e[e["made_playoffs"] == 0]["matches_played"].values

bp = ax.boxplot([playoff, non_playoff], patch_artist=True, notch=False,
                medianprops=dict(color="white", linewidth=2.5),
                whiskerprops=dict(linewidth=1.2),
                capprops=dict(linewidth=1.2),
                flierprops=dict(marker="o", markersize=4, alpha=0.5, linestyle="none"))

bp["boxes"][0].set_facecolor("#e07b39"); bp["boxes"][0].set_alpha(0.85)
bp["boxes"][1].set_facecolor("#3a86ff"); bp["boxes"][1].set_alpha(0.85)

p_med = np.median(playoff)
np_med = np.median(non_playoff)
ax.text(1.3, p_med, f"  {p_med:.0f}", va="center", fontsize=10, color="#333")
ax.text(2.3, np_med, f"  {np_med:.0f}", va="center", fontsize=10, color="#333")

ax.set_xticklabels(["Playoff Teams", "Non-Playoff Teams"])
ax.set_ylabel("Matches Played per Season")
ax.set_title(f"TNPL: Matches Played, Playoff vs. Non-Playoff Teams ({YEARS})", pad=12)
ax.tick_params(axis="x", length=0)
ax.grid(axis="x", visible=False)

# ~40 free runs per extra match: same top-batter heuristic as the IPL figure
extra = p_med - np_med
ax.annotate("",
            xy=(1.5, p_med), xytext=(1.5, np_med),
            arrowprops=dict(arrowstyle="<->", color="#555", lw=1.8))
ax.text(1.55, (p_med + np_med) / 2,
        f"+{extra:.0f} matches\n(~{extra * 40:.0f} free runs)",
        va="center", fontsize=9, color="#333")

fig.tight_layout()
save(fig, "fig6_match_count")


# ── Figure 7 — MOVI: strike rate, run leader vs best middle order ────────────
print("Figure 7: MOVI strike-rate dumbbell...")
fig, ax = plt.subplots(figsize=(7, 5.5))

leaders = bs.loc[bs.groupby("season")["runs"].idxmax()].set_index("season")
leaders["sr"] = leaders["runs"] / leaders["balls_faced"] * 100
dumb = moi.set_index("season")[["batter", "sr"]].rename(
    columns={"batter": "mo_name", "sr": "mo_sr"}).join(
    leaders[["batter", "sr"]].rename(columns={"batter": "oc_name", "sr": "oc_sr"}))
dumb = dumb.sort_index()

for season, r_ in dumb.iterrows():
    ax.plot([r_["oc_sr"], r_["mo_sr"]], [season, season],
            color="#999", linewidth=1.6, zorder=2)
ax.scatter(dumb["oc_sr"], dumb.index, color="#e07b39", s=70, zorder=3,
           edgecolors="#7a4a1f", linewidths=0.8, label="Most Runs winner (run leader)")
ax.scatter(dumb["mo_sr"], dumb.index, color="#3a86ff", s=70, zorder=3,
           edgecolors="#1c4f9c", linewidths=0.8, label="Best middle order (MOVI #1)")

ax.set_yticks(dumb.index)
ax.invert_yaxis()
ax.set_xlabel("Season Strike Rate (runs per 100 balls)")
ax.set_title("TNPL: Who Struck Faster — Run Leader vs Best Middle Order?", pad=12)
ax.legend(fontsize=9, loc="lower right")
ax.grid(axis="y", visible=False)

faster = int((dumb["mo_sr"] > dumb["oc_sr"]).sum())
gap = (dumb["mo_sr"] - dumb["oc_sr"]).mean()
ax.text(0.03, 0.03,
        f"MOVI #1 struck faster in {faster} of {len(dumb)} seasons\n"
        f"(avg gap: {gap:+.0f} runs per 100 balls)",
        transform=ax.transAxes, ha="left", va="bottom", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#f0f6ff", edgecolor="#3a86ff"))

fig.tight_layout()
save(fig, "fig7_movi_strike_rates")

print("\nAll 7 figures saved to TNPL/figures/")
