"""
Standalone, share-only MOVI app (Middle-Order Value Index).

A trimmed public version for sharing — shows only the MOVI section, with a
high-level description that does NOT expose the exact formula, weights, or the
wider Orange Cap bias study. Mobile-first layout. Run: streamlit run app_movi.py
"""

import os
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="MOVI — Middle-Order Value Index", page_icon="🏏",
                   layout="centered", initial_sidebar_state="collapsed")

GOLD, BLUE, ORANGE, GREY = "#FFC300", "#3a86ff", "#e07b39", "#adb5bd"
# Plotly: hide the toolbar (overlaps on phones) and stay responsive to width.
PCFG = {"displayModeBar": False, "responsive": True}

# Small CSS touch-ups for narrow screens (tighter padding, readable metrics).
st.markdown("""
<style>
.block-container {padding-top: 2rem; padding-bottom: 2rem;}
[data-testid="stMetricValue"] {font-size: 1.15rem;}
[data-testid="stMetricLabel"] {font-size: 0.8rem;}
</style>
""", unsafe_allow_html=True)

BASE = Path("outputs/tables")
DATA_FILES = {
    "moi_best": BASE / "middle_order_index_best.csv",
    "moi_all":  BASE / "middle_order_index_all.csv",
    "bs":       BASE / "batter_season.csv",
    "rec":      Path("data/reference/movi_recognition.csv"),
}


@st.cache_data
def load_data(data_version):
    return {k: pd.read_csv(p) for k, p in DATA_FILES.items()}


d = load_data(tuple(os.path.getmtime(p) for p in DATA_FILES.values()))
moi_best = d["moi_best"].copy()
moi_all = d["moi_all"].copy()
OC_WINNERS = d["bs"].loc[d["bs"].groupby("season")["runs"].idxmax()].set_index("season")

COMP_COLS = ["z_volume", "z_efficiency", "z_finishing", "z_consistency"]
COMP_LABELS = {
    "z_volume": "Volume (runs/inns)",
    "z_efficiency": "Efficiency (strike rate)",
    "z_finishing": "Finishing (death overs)",
    "z_consistency": "Consistency (median)",
}


def bar_layout(fig, xtitle, height):
    fig.update_layout(
        xaxis_title=xtitle, yaxis_title="", height=height,
        margin=dict(l=8, r=8, t=8, b=8), font=dict(size=13),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig


# ── Header ──────────────────────────────────────────────────────────────────
st.title("🏏 MOVI")
st.markdown("##### The Middle-Order Value Index")
st.markdown(
    "IPL run charts reward whoever *accumulates* the most — almost always an "
    "opener. **MOVI** asks instead: who was the best **middle-order** batsman each "
    "season? It rates every qualifying middle-order batsman (positions 4–7, 7+ "
    "matches) on four things — **Volume**, **Efficiency**, **Finishing** and "
    "**Consistency** — and blends them into one score, comparable within each "
    "season. Higher MOVI = stood further above his middle-order peers that year."
)
st.divider()

# ── Headline callouts ───────────────────────────────────────────────────────
win_counts = moi_best["batter"].value_counts()
repeats = win_counts[win_counts >= 2]
top_season = moi_best.loc[moi_best["index"].idxmax()]
g1, g2, g3 = st.columns(3)
g1.metric("Seasons", f"{moi_best['season'].nunique()}", "2008–2026")
g2.metric("Most-crowned", f"{int(repeats.max())}× each",
          ", ".join(repeats[repeats == repeats.max()].index.tolist()))
g3.metric("Best season", f"{top_season['index']:.2f}",
          f"{top_season['batter']} ({int(top_season['season'])})")
st.divider()

# ── Top 5 of the latest season (hero bar) ───────────────────────────────────
latest = int(moi_all["season"].max())
t5 = (moi_all[moi_all["season"] == latest]
      .sort_values("index", ascending=False).head(5).reset_index(drop=True))
st.subheader(f"🏆 Top 5 MOVI — {latest}")
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

# ── Season explorer (charts stacked, full width for mobile) ─────────────────
st.subheader("Explore any season")
season = st.selectbox("Season", sorted(moi_all["season"].unique()),
                      index=int(moi_all["season"].nunique() - 1), key="movi_season")
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
comp = pd.DataFrame({"Component": [COMP_LABELS[c] for c in COMP_COLS],
                     "v": [winner[c] for c in COMP_COLS]})
comp_colors = [ORANGE if v >= 0 else GREY for v in comp["v"]]
fig_c = go.Figure(go.Bar(
    x=comp["v"], y=comp["Component"], orientation="h", marker_color=comp_colors,
    text=[f"{v:+.2f}" for v in comp["v"]], textposition="outside"))
fig_c.add_vline(x=0, line_color="#888", line_width=1)
fig_c.update_layout(xaxis=dict(range=[comp["v"].min() - 1, comp["v"].max() + 1]))
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
st.dataframe(show, use_container_width=True, hide_index=True, height=430)
st.caption("The three highest-MOVI middle-order batsmen of every season. "
           "Swipe the table sideways to see every column.")
st.divider()

# ── Recurring winners ───────────────────────────────────────────────────────
st.subheader("The uncrowned regulars")
rc = win_counts[win_counts >= 2].sort_values()
fig_r = go.Figure(go.Bar(x=rc.values, y=rc.index, orientation="h", marker_color=BLUE,
                         text=[f"  {v}×" for v in rc.values], textposition="outside"))
fig_r.update_layout(xaxis=dict(dtick=1, range=[0, rc.values.max() + 0.6]))
st.plotly_chart(bar_layout(fig_r, "Seasons as best middle-order batsman", 240),
                use_container_width=True, config=PCFG)
st.divider()

# ── Did the league recognise them? ──────────────────────────────────────────
st.subheader("Did the league even notice?")
rec = moi_best[["season", "batter"]].merge(d["rec"], on="season", how="left")
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
    f"In **{unrec} of {len(rec)}** seasons the best middle-order batsman won no "
    "individual IPL award that season. Only Andre Russell (2015, 2019) was "
    "recognised — and through the all-rounder MVP, not a batting award. "
    "(2026 awards provisional.)")
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
