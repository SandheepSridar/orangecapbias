"""
Standalone, share-only MOVI app (Middle-Order Value Index).

A trimmed public version for sharing — shows only the MOVI section, with a
high-level description that does NOT expose the exact formula, weights, or the
wider Orange Cap bias study. Run:  streamlit run app_movi.py
"""

import os
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="MOVI — Middle-Order Value Index", page_icon="🏏", layout="wide")

GOLD, BLUE, ORANGE, GREY = "#FFC300", "#3a86ff", "#e07b39", "#adb5bd"
BASE = Path("outputs/tables")
DATA_FILES = {
    "moi_best": BASE / "middle_order_index_best.csv",
    "moi_all":  BASE / "middle_order_index_all.csv",
    "bs":       BASE / "batter_season.csv",
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

# ── Header ──────────────────────────────────────────────────────────────────
st.title("🏏 MOVI — The Middle-Order Value Index")
st.markdown(
    "The IPL's run charts reward whoever *accumulates* the most — which almost "
    "always means an opener. **MOVI** asks a different question: who was the best "
    "**middle-order** batsman each season? It rates every qualifying middle-order "
    "batsman (batting positions 4–7, 7+ matches) on four things — **Volume**, "
    "**Efficiency**, **Finishing** and **Consistency** — and blends them into a "
    "single score that is comparable within each season. The higher the MOVI, the "
    "more a batsman stood above his middle-order peers that year."
)
st.divider()

# ── Headline callouts ───────────────────────────────────────────────────────
win_counts = moi_best["batter"].value_counts()
repeats = win_counts[win_counts >= 2]
top_season = moi_best.loc[moi_best["index"].idxmax()]
g1, g2, g3 = st.columns(3)
g1.metric("Seasons covered", f"{moi_best['season'].nunique()}", "2008 – 2026")
g2.metric("Most-crowned", ", ".join(repeats[repeats == repeats.max()].index.tolist()),
          f"{int(repeats.max())}× each")
g3.metric("Most dominant season", f"{top_season['batter']} ({int(top_season['season'])})",
          f"MOVI {top_season['index']:.2f}")
st.divider()

# ── Top 5 of the latest season ──────────────────────────────────────────────
latest = int(moi_all["season"].max())
t5 = (moi_all[moi_all["season"] == latest]
      .sort_values("index", ascending=False).head(5).reset_index(drop=True))
st.subheader(f"🏆 Top 5 MOVI — {latest}")
medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
cols = st.columns(5)
for i, (col, (_, r)) in enumerate(zip(cols, t5.iterrows())):
    col.metric(f"{medals[i]} {r['batter']}", f"{r['index']:.2f}",
               f"{int(r['runs'])} runs · SR {r['sr']:.0f}")
st.caption(f"The five highest-rated middle-order batsmen of {latest}, by MOVI.")
st.divider()

# ── Season explorer ─────────────────────────────────────────────────────────
season = st.selectbox("Explore a season", sorted(moi_all["season"].unique()),
                      index=int(moi_all["season"].nunique() - 1), key="movi_season")
sdf = moi_all[moi_all["season"] == season].sort_values("index", ascending=False)
topn = sdf.head(8).copy()
winner = topn.iloc[0]

left, right = st.columns([3, 2])
with left:
    st.markdown(f"**Top middle-order batsmen — {season}**")
    bar_colors = [GOLD if i == 0 else BLUE for i in range(len(topn))]
    fig = go.Figure(go.Bar(
        x=topn["index"], y=topn["batter"], orientation="h", marker_color=bar_colors,
        customdata=topn[["team", "avg_pos", "matches", "runs", "sr", "death_sr"]].values,
        hovertemplate=("<b>%{y}</b> — %{customdata[0]}<br>MOVI: %{x:.2f}<br>"
                       "Avg position: %{customdata[1]:.1f}<br>Matches: %{customdata[2]} · "
                       "Runs: %{customdata[3]}<br>Strike rate: %{customdata[4]:.1f} · "
                       "Death SR: %{customdata[5]:.1f}<extra></extra>")))
    fig.update_layout(xaxis_title="MOVI", yaxis_title="",
                      yaxis=dict(categoryorder="total ascending"),
                      height=360, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("🥇 Gold = the season's top middle-order batsman.")

with right:
    st.markdown(f"**What set {winner['batter']} apart**")
    comp = pd.DataFrame({"Component": [COMP_LABELS[c] for c in COMP_COLS],
                         "v": [winner[c] for c in COMP_COLS]})
    comp_colors = [ORANGE if v >= 0 else GREY for v in comp["v"]]
    fig_c = go.Figure(go.Bar(
        x=comp["v"], y=comp["Component"], orientation="h", marker_color=comp_colors,
        text=[f"{v:+.2f}" for v in comp["v"]], textposition="outside"))
    fig_c.add_vline(x=0, line_color="#333", line_width=1)
    fig_c.update_layout(xaxis_title="Relative strength (vs season's middle order)",
                        yaxis_title="", height=360, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_c, use_container_width=True)
    st.caption("How far above (orange) or below (grey) the season's middle-order "
               "average this batsman ranked on each skill.")
st.divider()

# ── Leaderboard ─────────────────────────────────────────────────────────────
st.markdown("**Best middle-order batsman, every season (2008–2026)**")
show = moi_best[["season", "batter", "team", "avg_pos", "matches", "runs",
                 "sr", "death_sr", "index"]].rename(columns={
    "avg_pos": "Avg Pos", "sr": "Strike Rate", "death_sr": "Death SR", "index": "MOVI"})
st.dataframe(show, use_container_width=True, hide_index=True)

# ── Recurring winners ───────────────────────────────────────────────────────
st.markdown("**The uncrowned regulars** — players who top MOVI most often")
rc = win_counts[win_counts >= 2].sort_values()
fig_r = go.Figure(go.Bar(x=rc.values, y=rc.index, orientation="h", marker_color=BLUE,
                         text=[f"{v}×" for v in rc.values], textposition="outside"))
fig_r.update_layout(xaxis_title="Seasons as best middle-order batsman", yaxis_title="",
                    height=260, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(dtick=1))
st.plotly_chart(fig_r, use_container_width=True)
st.divider()

# ── Crowned vs uncrowned strike-rate dumbbell ───────────────────────────────
st.markdown("**Who actually struck faster — the run-leader, or the best middle order?**")
oc_sr = OC_WINNERS.reset_index()[["season", "batter", "runs", "balls_faced"]].copy()
oc_sr["oc_sr"] = oc_sr["runs"] / oc_sr["balls_faced"] * 100
dumb = (oc_sr.rename(columns={"batter": "oc_name"})
        .merge(moi_best[["season", "batter", "sr"]].rename(
            columns={"batter": "mo_name", "sr": "mo_sr"}), on="season")
        .sort_values("season"))
fig_d = go.Figure()
for _, r in dumb.iterrows():
    fig_d.add_trace(go.Scatter(x=[r["oc_sr"], r["mo_sr"]], y=[r["season"], r["season"]],
                               mode="lines", line=dict(color="#d3d3d3", width=2),
                               showlegend=False, hoverinfo="skip"))
fig_d.add_trace(go.Scatter(
    x=dumb["oc_sr"], y=dumb["season"], mode="markers",
    marker=dict(color=ORANGE, size=10, line=dict(color="#7a4a1f", width=1)),
    name="Season's run-leader", customdata=dumb[["oc_name"]].values,
    hovertemplate="<b>%{customdata[0]}</b> (%{y})<br>Strike rate %{x:.1f}<extra></extra>"))
fig_d.add_trace(go.Scatter(
    x=dumb["mo_sr"], y=dumb["season"], mode="markers",
    marker=dict(color=BLUE, size=10, line=dict(color="#1c4f9c", width=1)),
    name="Best middle-order batsman", customdata=dumb[["mo_name"]].values,
    hovertemplate="<b>%{customdata[0]}</b> (%{y})<br>Strike rate %{x:.1f}<extra></extra>"))
fig_d.update_layout(xaxis_title="Season strike rate", yaxis_title="",
                    yaxis=dict(dtick=1, autorange="reversed"), height=560,
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
st.plotly_chart(fig_d, use_container_width=True)
faster = int((dumb["mo_sr"] > dumb["oc_sr"]).sum())
gap = (dumb["mo_sr"] - dumb["oc_sr"]).mean()
st.caption(
    f"Orange = the season's leading run-scorer; blue = the best middle-order batsman. "
    f"In **{faster} of {len(dumb)}** seasons the middle-order batsman struck faster, by "
    f"an average of **{gap:.0f} runs per 100 balls**.")

st.divider()
st.caption("MOVI — Middle-Order Value Index · Data: Cricsheet IPL ball-by-ball (2008–2026).")
