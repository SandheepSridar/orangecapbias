"""
Standalone, share-only MOVI app (Middle-Order Value Index).

A trimmed public version for sharing. Shows only the MOVI section, with a
high-level description that does NOT expose the exact formula, weights, or the
wider Orange Cap bias study. Mobile-first. The minimum-matches threshold is
adjustable: MOVI is recomputed live from a components file (every middle-order
batter-season with its raw metrics), so changing the threshold re-scores the
whole index within each season. Run: streamlit run app_movi.py
"""

import os
from pathlib import Path

import streamlit as st
import pandas as pd

st.set_page_config(page_title="MOVI — Middle-Order Value Index", page_icon="🏏",
                   layout="centered", initial_sidebar_state="collapsed")
import plotly.graph_objects as go

GOLD, BLUE, ORANGE, GREY = "#FFC300", "#3a86ff", "#e07b39", "#adb5bd"
PCFG = {"displayModeBar": False, "responsive": True}
DEFAULT_MIN_MATCHES = 7
DEFAULT_POS_MIN = 4.0
POS_MAX = 7  # upper bound of the middle-order band — fixed

st.markdown("""
<style>
.block-container {padding-top: 2rem; padding-bottom: 2rem;}
[data-testid="stMetricValue"] {font-size: 1.15rem;}
[data-testid="stMetricLabel"] {font-size: 0.8rem;}
</style>
""", unsafe_allow_html=True)

BASE = Path("outputs/tables")
DATA_FILES = {
    "comp": BASE / "middle_order_components.csv",
    "bs":   BASE / "batter_season.csv",
    "rec":  Path("data/reference/movi_recognition.csv"),
}

COMP_COLS = ["z_volume", "z_efficiency", "z_finishing", "z_consistency"]
COMP_LABELS = {
    "z_volume": "Volume (runs/inns)",
    "z_efficiency": "Efficiency (strike rate)",
    "z_finishing": "Finishing (death overs)",
    "z_consistency": "Consistency (median)",
}


@st.cache_data
def load_data(data_version):
    return {k: pd.read_csv(p) for k, p in DATA_FILES.items()}


@st.cache_data
def compute_movi(comp, min_matches, pos_min):
    """Re-score MOVI from raw components at a given threshold and position band.

    Keeps batters with average position in [pos_min, POS_MAX] who played at least
    min_matches. Each of the four components is standardised (z-score) within its
    season over the qualifying pool, then averaged with equal weight. Batters with
    no death-overs balls take the season-mean finishing value (neutral).
    """
    df = comp[(comp["matches"] >= min_matches)
              & (comp["avg_pos"] >= pos_min) & (comp["avg_pos"] <= POS_MAX)].copy()
    df["death_sr_f"] = df.groupby("season")["death_sr"].transform(lambda s: s.fillna(s.mean()))

    def z(s):
        sd = s.std(ddof=1)
        return (s - s.mean()) / sd if sd and not pd.isna(sd) else s * 0.0

    for col, zc in [("mean_rpi", "z_volume"), ("sr", "z_efficiency"),
                    ("death_sr_f", "z_finishing"), ("median_rpi", "z_consistency")]:
        df[zc] = df.groupby("season")[col].transform(z)
    df["index"] = df[COMP_COLS].mean(axis=1)
    df["season_rank"] = df.groupby("season")["index"].rank(ascending=False, method="min").astype(int)
    return df


def bar_layout(fig, xtitle, height):
    fig.update_layout(xaxis_title=xtitle, yaxis_title="", height=height,
                      margin=dict(l=8, r=8, t=8, b=8), font=dict(size=13),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig


d = load_data(tuple(os.path.getmtime(p) for p in DATA_FILES.values()))
comp = d["comp"]
OC_WINNERS = d["bs"].loc[d["bs"].groupby("season")["runs"].idxmax()].set_index("season")

# ── Header ──────────────────────────────────────────────────────────────────
st.title("🏏 MOVI")
st.markdown("##### The Middle-Order Value Index")
st.markdown(
    "IPL run charts reward whoever *accumulates* the most — almost always an "
    "opener. **MOVI** asks instead: who was the best **middle-order** batsman each "
    "season? It rates every qualifying middle-order batsman (positions 4–7) on four "
    "things — **Volume**, **Efficiency**, **Finishing** and **Consistency** — and "
    "blends them into one score, comparable within each season. Higher MOVI = stood "
    "further above his middle-order peers that year."
)

# ── Threshold controls ──────────────────────────────────────────────────────
POS_OPTIONS = [3.75, 3.80, 3.85, 3.90, 3.95, 4.00]
min_matches = st.segmented_control(
    "Minimum matches to qualify in a season", options=list(range(5, 15)),
    default=DEFAULT_MIN_MATCHES, key="movi_minmatches",
    help="MOVI is recomputed live. A higher bar removes small-sample seasons; a "
         "lower bar lets in players who featured in fewer games.")
min_matches = DEFAULT_MIN_MATCHES if min_matches is None else min_matches
st.caption("💡 Suggested: keep this at **7** so short cameo bursts aren't "
           "over-weighted against players who batted a full season.")
pos_min = st.segmented_control(
    "Lowest average batting position to include", options=POS_OPTIONS,
    default=DEFAULT_POS_MIN, format_func=lambda x: f"{x:.2f}", key="movi_posmin",
    help=f"The middle-order band is [this value, {POS_MAX}]. The upper bound is "
         f"fixed at {POS_MAX}. Lowering this admits batsmen who average just below "
         "4 (floating No. 3–4s).")
pos_min = DEFAULT_POS_MIN if pos_min is None else pos_min
st.caption("💡 Suggested: keep this at **4** — that isolates *true* middle-order "
           "batsmen. Lower values let in floating No. 3–4s, which dilutes the group.")
moi_all = compute_movi(comp, min_matches, pos_min)
moi_best = moi_all.loc[moi_all.groupby("season")["index"].idxmax()].sort_values("season")
if min_matches != DEFAULT_MIN_MATCHES or pos_min != DEFAULT_POS_MIN:
    st.caption(f"Showing MOVI for positions **{pos_min:g}–{POS_MAX}** at a "
               f"**{min_matches}-match** minimum "
               f"(defaults: {DEFAULT_POS_MIN:g}–{POS_MAX}, {DEFAULT_MIN_MATCHES} matches).")
st.divider()

# ── Headline callouts ───────────────────────────────────────────────────────
win_counts = moi_best["batter"].value_counts()
repeats = win_counts[win_counts >= 2]
top_season = moi_best.loc[moi_best["index"].idxmax()]
g1, g2, g3 = st.columns(3)
g1.metric("Seasons", f"{moi_best['season'].nunique()}", "2008–2026")
g2.metric("Most-crowned",
          f"{int(repeats.max())}× each" if not repeats.empty else "—",
          ", ".join(repeats[repeats == repeats.max()].index.tolist()) if not repeats.empty else "no repeats")
g3.metric("Best season", f"{top_season['index']:.2f}",
          f"{top_season['batter']} ({int(top_season['season'])})")
st.divider()

# ── Top 5 of the latest season (hero bar) ───────────────────────────────────
latest = int(moi_all["season"].max())
t5 = (moi_all[moi_all["season"] == latest]
      .sort_values("index", ascending=False).head(5).reset_index(drop=True))
st.subheader(f"🏆 Top {len(t5)} MOVI — {latest}")
t5_colors = [GOLD] + [BLUE] * (len(t5) - 1)
fig_t5 = go.Figure(go.Bar(
    x=t5["index"], y=t5["batter"], orientation="h", marker_color=t5_colors,
    text=[f"  {v:.2f}" for v in t5["index"]], textposition="outside",
    customdata=t5[["team", "runs", "sr"]].values,
    hovertemplate=("<b>%{y}</b> — %{customdata[0]}<br>MOVI: %{x:.2f}<br>"
                   "Runs: %{customdata[1]} · SR: %{customdata[2]:.0f}<extra></extra>")))
fig_t5.update_layout(yaxis=dict(categoryorder="total ascending"),
                     xaxis=dict(range=[0, t5["index"].max() * 1.18]))
st.plotly_chart(bar_layout(fig_t5, "MOVI", 280), use_container_width=True, config=PCFG)
st.caption(f"🥇 {t5.iloc[0]['batter']} leads {latest} "
           f"({int(t5.iloc[0]['runs'])} runs, SR {t5.iloc[0]['sr']:.0f}).")
st.divider()

# ── Season explorer ─────────────────────────────────────────────────────────
st.subheader("Explore any season")
seasons = sorted(moi_all["season"].unique())
season = st.selectbox("Season", seasons, index=len(seasons) - 1, key="movi_season")
sdf = moi_all[moi_all["season"] == season].sort_values("index", ascending=False)
topn = sdf.head(8).copy()
winner = topn.iloc[0]

st.markdown(f"**Top middle-order batsmen — {season}**")
bar_colors = [GOLD if i == 0 else BLUE for i in range(len(topn))]
fig = go.Figure(go.Bar(
    x=topn["index"], y=topn["batter"], orientation="h", marker_color=bar_colors,
    customdata=topn[["team", "avg_pos", "matches", "runs", "sr", "death_sr"]].values,
    hovertemplate=("<b>%{y}</b> — %{customdata[0]}<br>MOVI: %{x:.2f}<br>"
                   "Avg position: %{customdata[1]:.1f}<br>Matches: %{customdata[2]} · "
                   "Runs: %{customdata[3]}<br>Strike rate: %{customdata[4]:.1f} · "
                   "Death SR: %{customdata[5]:.1f}<extra></extra>")))
fig.update_layout(yaxis=dict(categoryorder="total ascending"))
st.plotly_chart(bar_layout(fig, "MOVI", 330), use_container_width=True, config=PCFG)
st.caption("🥇 Gold = the season's top middle-order batsman.")

st.markdown(f"**What set {winner['batter']} apart**")
compdf = pd.DataFrame({"Component": [COMP_LABELS[c] for c in COMP_COLS],
                       "v": [winner[c] for c in COMP_COLS]})
comp_colors = [ORANGE if v >= 0 else GREY for v in compdf["v"]]
fig_c = go.Figure(go.Bar(
    x=compdf["v"], y=compdf["Component"], orientation="h", marker_color=comp_colors,
    text=[f"{v:+.2f}" for v in compdf["v"]], textposition="outside"))
fig_c.add_vline(x=0, line_color="#888", line_width=1)
fig_c.update_layout(xaxis=dict(range=[compdf["v"].min() - 1, compdf["v"].max() + 1]))
st.plotly_chart(bar_layout(fig_c, "Relative strength (vs season's middle order)", 300),
                use_container_width=True, config=PCFG)
st.caption("How far above (orange) or below (grey) the season's middle-order "
           "average this batsman ranked on each skill.")
st.divider()

# ── Leaderboard: top 3 every season ─────────────────────────────────────────
st.subheader("Top 3 every season (2008–2026)")
top3 = moi_all[moi_all["season_rank"] <= 3].sort_values(["season", "season_rank"]).copy()
top3["Rank"] = top3["season_rank"].map({1: "🥇", 2: "🥈", 3: "🥉"})
show = top3[["season", "Rank", "batter", "team", "runs", "sr", "index"]].rename(columns={
    "season": "Season", "batter": "Batsman", "team": "Team",
    "runs": "Runs", "sr": "SR", "index": "MOVI"})
show["SR"] = show["SR"].round(1)
show["MOVI"] = show["MOVI"].round(2)
st.dataframe(show, use_container_width=True, hide_index=True, height=430)
st.caption("The three highest-MOVI middle-order batsmen of every season. "
           "Swipe the table sideways to see every column.")
st.divider()

# ── Recurring winners ───────────────────────────────────────────────────────
if not repeats.empty:
    st.subheader("The uncrowned regulars")
    rc = repeats.sort_values()
    fig_r = go.Figure(go.Bar(x=rc.values, y=rc.index, orientation="h", marker_color=BLUE,
                             text=[f"  {v}×" for v in rc.values], textposition="outside"))
    fig_r.update_layout(xaxis=dict(dtick=1, range=[0, rc.values.max() + 0.6]))
    st.plotly_chart(bar_layout(fig_r, "Seasons as best middle-order batsman", 240),
                    use_container_width=True, config=PCFG)
    st.divider()

# ── Did the league recognise them? (fixed at the standard threshold) ─────────
st.subheader("Did the league even notice?")
rec_all = compute_movi(comp, DEFAULT_MIN_MATCHES, DEFAULT_POS_MIN)
rec_best = rec_all.loc[rec_all.groupby("season")["index"].idxmax()].sort_values("season")
rec = rec_best[["season", "batter"]].merge(d["rec"], on=["season", "batter"], how="left")
rec["other_award"] = rec["other_award"].fillna("").astype(str).str.strip()
unrec = int((rec["other_award"] == "").sum())
st.metric("Seasons with no other award", f"{unrec} of {len(rec)}",
          "MOVI #1 won no individual IPL award that season")
rec_tbl = rec.copy()
rec_tbl["other_award"] = rec_tbl["other_award"].replace("", "—")
rec_tbl = rec_tbl.rename(columns={
    "season": "Season", "batter": "MOVI #1", "other_award": "Other award that season"})
st.dataframe(rec_tbl, use_container_width=True, hide_index=True, height=430)
st.caption(
    f"At the standard {DEFAULT_MIN_MATCHES}-match qualification, in **{unrec} of "
    f"{len(rec)}** seasons the best middle-order batsman won no individual IPL award "
    "that season. Only Andre Russell (2015, 2019) was recognised — and through the "
    "all-rounder MVP, not a batting award. (This panel is fixed at the standard "
    "threshold; 2026 awards provisional.)")
st.divider()

# ── Crowned vs uncrowned strike-rate dumbbell ───────────────────────────────
st.subheader("Who actually struck faster?")
oc_sr = OC_WINNERS.reset_index()[["season", "batter", "runs", "balls_faced"]].copy()
oc_sr["oc_sr"] = oc_sr["runs"] / oc_sr["balls_faced"] * 100
dumb = (oc_sr.rename(columns={"batter": "oc_name"})
        .merge(moi_best[["season", "batter", "sr"]].rename(
            columns={"batter": "mo_name", "sr": "mo_sr"}), on="season")
        .sort_values("season"))
fig_d = go.Figure()
for _, r in dumb.iterrows():
    fig_d.add_trace(go.Scatter(x=[r["oc_sr"], r["mo_sr"]], y=[r["season"], r["season"]],
                               mode="lines", line=dict(color="#555", width=2),
                               showlegend=False, hoverinfo="skip"))
fig_d.add_trace(go.Scatter(
    x=dumb["oc_sr"], y=dumb["season"], mode="markers",
    marker=dict(color=ORANGE, size=10, line=dict(color="#7a4a1f", width=1)),
    name="Run-leader", customdata=dumb[["oc_name"]].values,
    hovertemplate="<b>%{customdata[0]}</b> (%{y})<br>SR %{x:.1f}<extra></extra>"))
fig_d.add_trace(go.Scatter(
    x=dumb["mo_sr"], y=dumb["season"], mode="markers",
    marker=dict(color=BLUE, size=10, line=dict(color="#1c4f9c", width=1)),
    name="Best middle order", customdata=dumb[["mo_name"]].values,
    hovertemplate="<b>%{customdata[0]}</b> (%{y})<br>SR %{x:.1f}<extra></extra>"))
fig_d.update_layout(yaxis=dict(dtick=1, autorange="reversed"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0))
st.plotly_chart(bar_layout(fig_d, "Season strike rate", 620),
                use_container_width=True, config=PCFG)
faster = int((dumb["mo_sr"] > dumb["oc_sr"]).sum())
gap = (dumb["mo_sr"] - dumb["oc_sr"]).mean()
st.caption(
    f"Orange = the season's leading run-scorer; blue = the best middle-order "
    f"batsman. In **{faster} of {len(dumb)}** seasons the middle-order batsman "
    f"struck faster, by an average of **{gap:.0f} runs per 100 balls**.")

st.divider()
st.caption("MOVI — Middle-Order Value Index · Data: Cricsheet IPL ball-by-ball (2008–2026).")
