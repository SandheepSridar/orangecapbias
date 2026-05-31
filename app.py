import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(
    page_title="IPL Orange Cap Bias",
    page_icon="🏏",
    layout="wide",
)

POSITION_ORDER = ["Opener (1-2)", "Top Order (3)", "Middle Order (4-5)", "Finisher (6+)"]
POSITION_COLORS = {
    "Opener (1-2)":       "#e07b39",
    "Top Order (3)":      "#f5c518",
    "Middle Order (4-5)": "#3a86ff",
    "Finisher (6+)":      "#8ecae6",
}
PHASE_COLORS = {
    "Powerplay (1-6)": "#e07b39",
    "Middle (7-15)":   "#3a86ff",
    "Death (16-20)":   "#6c757d",
}

BASE = Path("outputs/tables")


@st.cache_data
def load_data():
    return {
        "a":  pd.read_csv(BASE / "analysis_a_winner_positions.csv"),
        "b":  pd.read_csv(BASE / "analysis_b_balls_faced_by_position.csv"),
        "c":  pd.read_csv(BASE / "analysis_c_powerplay_concentration.csv"),
        "d":  pd.read_csv(BASE / "analysis_d_normalised_rankings.csv"),
        "e":  pd.read_csv(BASE / "analysis_e_playoff_match_advantage.csv"),
        "f":  pd.read_csv(BASE / "analysis_f_non_playoff_elite.csv"),
        "bs": pd.read_csv(BASE / "batter_season.csv"),
        "oc": pd.read_csv("data/reference/orange_cap_winners.csv"),
    }


d = load_data()

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🏏 IPL Orange Cap: A Structural Bias Analysis")
st.markdown(
    """
    The IPL Orange Cap goes to the highest run-scorer each season.
    This analysis asks: **is that fair?** Ball-by-ball data from all 18 complete
    IPL seasons (2008–2025) shows the award structurally disadvantages middle-order
    batsmen and players on non-playoff teams — not due to skill, but due to design.
    """
)

st.divider()

# ── Key callouts ──────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Seasons Analysed", "18", "2008 – 2025")
c2.metric("Opener/Top-3 Winners", "18 / 18", "100% of all time")
c3.metric("Extra Balls (Openers vs Middle)", "+43 / season", "median, p < 0.001")
c4.metric("Non-Playoff Elite Cases", "23", "top-5 despite fewer matches")

st.divider()

ANALYSES = [
    "A · Winner Positions",
    "B · Balls Faced",
    "C · Powerplay Access",
    "D · Normalised Rankings",
    "E · Playoff Advantage",
    "F · Non-Playoff Elites",
]
tab = st.sidebar.radio("Analysis", ANALYSES, key="active_tab")

# ── Tab A — Winner Positions ──────────────────────────────────────────────────
if tab == "A · Winner Positions":
    st.subheader("Who wins the Orange Cap? Always the top order.")

    a = d["a"].copy()
    counts = a["position_group"].value_counts().reindex(POSITION_ORDER, fill_value=0).reset_index()
    counts.columns = ["position_group", "winners"]

    fig = px.bar(
        counts,
        x="position_group", y="winners",
        color="position_group",
        color_discrete_map=POSITION_COLORS,
        labels={"position_group": "Batting Position Group", "winners": "Orange Cap Winners"},
        text="winners",
        category_orders={"position_group": POSITION_ORDER},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=False, yaxis_range=[0, 18])
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Season-by-season breakdown**")
    a_display = a[["season", "winner", "team", "total_runs", "avg_batting_position", "position_group", "playoff_team"]]
    st.dataframe(a_display, use_container_width=True, hide_index=True)

    st.info(
        "**Finding:** 15 out of 18 winners (83%) batted at positions 1–2. "
        "The remaining 3 all batted at position 3. No middle-order or finisher has ever won."
    )


# ── Tab B — Balls Faced ───────────────────────────────────────────────────────
elif tab == "B · Balls Faced":
    st.subheader("Openers face significantly more balls per season.")

    bs = d["bs"]

    fig = px.box(
        bs[bs["position_group"].isin(POSITION_ORDER)],
        x="position_group", y="balls_faced",
        color="position_group",
        color_discrete_map=POSITION_COLORS,
        category_orders={"position_group": POSITION_ORDER},
        labels={"position_group": "Position Group", "balls_faced": "Balls Faced per Season"},
        points=False,
    )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    b = d["b"].set_index("position_group").reindex(POSITION_ORDER)
    st.markdown("**Summary statistics**")
    st.dataframe(
        b[["avg_balls", "median_balls", "min_balls", "max_balls", "batter_seasons"]].rename(columns={
            "avg_balls": "Mean", "median_balls": "Median",
            "min_balls": "Min", "max_balls": "Max", "batter_seasons": "N (batter-seasons)"
        }),
        use_container_width=True,
    )

    st.info(
        "**Finding:** Openers face a median of 43 more balls per season than middle-order batsmen. "
        "More balls = more opportunities to accumulate runs. This is a structural ceiling, not a skill gap."
    )


# ── Tab C — Powerplay Access ──────────────────────────────────────────────────
elif tab == "C · Powerplay Access":
    st.subheader("Middle-order batsmen cannot access the powerplay.")

    c = d["c"].copy()
    c_melted = c[["position_group", "pp_pct", "mid_pct", "death_pct"]].rename(columns={
        "pp_pct": "Powerplay (1-6)",
        "mid_pct": "Middle (7-15)",
        "death_pct": "Death (16-20)",
    })
    c_long = c_melted.melt(id_vars="position_group", var_name="Phase", value_name="% of Season Runs")

    fig = px.bar(
        c_long,
        x="position_group", y="% of Season Runs",
        color="Phase",
        color_discrete_map=PHASE_COLORS,
        barmode="stack",
        category_orders={"position_group": POSITION_ORDER},
        labels={"position_group": "Position Group"},
        text_auto=".1f",
    )
    fig.update_traces(textposition="inside", textfont_size=11)
    fig.update_layout(yaxis_range=[0, 105])
    st.plotly_chart(fig, use_container_width=True)

    st.info(
        "**Finding:** Openers score **57.5%** of their seasonal runs in the powerplay (overs 1–6). "
        "Middle-order batsmen score just **16.2%** there — most of them never bat in the powerplay at all. "
        "Powerplay conditions (fielding restrictions, fresh pitch) are systematically unavailable to them."
    )


# ── Tab D — Normalised Rankings ───────────────────────────────────────────────
elif tab == "D · Normalised Rankings":
    st.subheader("When you normalise for matches played, rankings change significantly.")

    d_df = d["d"].copy()

    season = st.selectbox("Select season", sorted(d_df["season"].unique()), index=0, key="d_season_select")
    season_df = d_df[d_df["season"] == season].copy()
    top10 = season_df[season_df["actual_rank"] <= 10].sort_values("actual_rank")

    fig = go.Figure()
    for _, row in top10.iterrows():
        color = "#e07b39" if row["actual_rank"] != row["norm_rank"] else "#adb5bd"
        fig.add_trace(go.Scatter(
            x=[0, 1],
            y=[row["actual_rank"], row["norm_rank"]],
            mode="lines+markers+text",
            line=dict(color=color, width=2),
            marker=dict(size=8, color=color),
            text=[f'{row["batter"]} ({int(row["league_runs"])})',
                  f'{row["batter"]} ({int(row["normalised_runs"])})'],
            textposition=["middle left", "middle right"],
            showlegend=False,
            hovertemplate=(
                f"<b>{row['batter']}</b><br>"
                f"Actual: #{int(row['actual_rank'])} ({int(row['league_runs'])} runs, {int(row['league_matches'])} matches)<br>"
                f"Normalised: #{int(row['norm_rank'])} ({int(row['normalised_runs']):.0f} runs @ 14 matches)"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        xaxis=dict(
            tickvals=[0, 1],
            ticktext=["Actual Ranking", "Normalised to 14 matches"],
            range=[-0.4, 1.4],
        ),
        yaxis=dict(autorange="reversed", title="Rank", dtick=1),
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Orange lines = rank changed after normalisation. Grey = rank unchanged.")

    shift_pct = (d_df[d_df["actual_rank"] <= 10]["actual_rank"] != d_df[d_df["actual_rank"] <= 10]["norm_rank"]).mean() * 100
    st.info(
        f"**Finding:** Across all 18 seasons, **{shift_pct:.1f}%** of top-10 batters have a different "
        "rank after normalising to a standard 14-match season (Wilcoxon signed-rank, p < 0.001). "
        "The award is sensitive to how many matches a player got to play."
    )

    # ── Confidence interval chart (only for batters with missing matches) ─────
    projected = season_df[season_df["missing_matches"] > 0].copy()
    if not projected.empty:
        st.markdown("#### Projection uncertainty for batters with fewer than 14 matches")

        oc_runs = int(season_df.sort_values("actual_rank").iloc[0]["league_runs"])

        projected = projected.sort_values("normalised_runs", ascending=True)
        ci_half = ((projected["ci_upper"] - projected["ci_lower"]) / 2).values

        fig_ci = go.Figure()
        fig_ci.add_trace(go.Scatter(
            x=projected["normalised_runs"],
            y=projected["batter"],
            mode="markers",
            marker=dict(size=10, color="#3a86ff"),
            error_x=dict(type="data", array=ci_half, color="#3a86ff", thickness=2, width=6),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Projected: %{x:.0f} runs<br>"
                "95% CI: [%{customdata[0]:.0f}, %{customdata[1]:.0f}]<br>"
                "Matches played: %{customdata[2]} of 14"
                "<extra></extra>"
            ),
            customdata=projected[["ci_lower", "ci_upper", "league_matches"]].values,
        ))
        fig_ci.add_vline(
            x=oc_runs,
            line_dash="dash", line_color="#e07b39", line_width=2,
            annotation_text=f"Actual #1: {oc_runs} runs",
            annotation_position="top right",
        )
        fig_ci.update_layout(
            xaxis_title="Projected runs (normalised to 14 matches)",
            yaxis_title="",
            height=max(250, len(projected) * 55),
            margin=dict(l=140),
        )
        st.plotly_chart(fig_ci, use_container_width=True)
        st.caption(
            "Dots = projected 14-match total. Bars = 95% confidence interval. "
            "Orange dashed line = actual season #1's run tally. "
            "Batters whose CI bar crosses the orange line had a plausible path to the Orange Cap."
        )


# ── Tab E — Playoff Advantage ─────────────────────────────────────────────────
elif tab == "E · Playoff Advantage":
    st.subheader("Playoff teams play ~2 more matches — that's ~80 free runs.")

    e = d["e"].copy()
    e["Playoff Status"] = e["made_playoffs"].map({1: "Playoff Team", 0: "Non-Playoff Team"})

    fig = px.strip(
        e,
        x="Playoff Status", y="matches_played",
        color="Playoff Status",
        color_discrete_map={"Playoff Team": "#e07b39", "Non-Playoff Team": "#3a86ff"},
        labels={"matches_played": "Matches Played"},
        hover_data=["season", "batting_team"],
    )
    fig.update_traces(jitter=0.4, marker_size=7, opacity=0.7)

    playoff_med = e[e["made_playoffs"] == 1]["matches_played"].median()
    non_playoff_med = e[e["made_playoffs"] == 0]["matches_played"].median()
    for val, label in [(playoff_med, "Playoff median"), (non_playoff_med, "Non-playoff median")]:
        fig.add_hline(
            y=val, line_dash="dot", line_color="#333",
            annotation_text=f"{label}: {val:.0f}", annotation_position="right",
        )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    st.info(
        f"**Finding:** Playoff teams play a median of **{playoff_med:.0f} matches** vs "
        f"**{non_playoff_med:.0f}** for non-playoff teams (Mann-Whitney U, p < 0.001). "
        "At ~40 runs per match, that's roughly **80 free runs** just for qualifying — "
        "enough to swing the Orange Cap in many seasons."
    )


# ── Tab F — Non-Playoff Elites ────────────────────────────────────────────────
elif tab == "F · Non-Playoff Elites":
    st.subheader("Non-playoff batsmen match elite output — with fewer matches.")

    f = d["f"].copy()
    oc = d["oc"].copy()

    f = f.merge(oc[["season", "winner", "total_runs"]], on="season", how="left")
    f = f.rename(columns={"total_runs": "oc_winner_runs"})

    f["would_have_beaten_oc"] = f["proj_runs_16_matches"] > f["oc_winner_runs"]

    fig = go.Figure()
    for _, row in f.iterrows():
        color = "#e07b39" if row["would_have_beaten_oc"] else "#3a86ff"
        fig.add_trace(go.Bar(
            name=f'{row["batter"]} ({row["season"]})',
            x=[f'{row["batter"]}<br>{row["season"]}'],
            y=[row["runs"]],
            marker_color="#3a86ff",
            showlegend=False,
            hovertemplate=(
                f"<b>{row['batter']} ({row['season']})</b><br>"
                f"Actual runs: {row['runs']}<br>"
                f"Matches played: {row['matches']}<br>"
                f"Projected (16 matches): {row['proj_runs_16_matches']}<br>"
                f"OC winner that year: {row['winner']} ({row['oc_winner_runs']} runs)"
                "<extra></extra>"
            ),
        ))
        fig.add_trace(go.Bar(
            x=[f'{row["batter"]}<br>{row["season"]}'],
            y=[row["proj_runs_16_matches"] - row["runs"]],
            marker_color=color,
            showlegend=False,
            hovertemplate=(
                f"Projected extra runs (to 16 matches): +{row['proj_runs_16_matches'] - row['runs']:.0f}"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        barmode="stack",
        xaxis_title="Batter (Season)",
        yaxis_title="Runs",
        legend_title="",
        height=480,
    )

    oc_by_season = {}
    for _, row in f.iterrows():
        oc_by_season[row["season"]] = row["oc_winner_runs"]

    for season_val, oc_runs in oc_by_season.items():
        season_rows = f[f["season"] == season_val]
        if len(season_rows) == 0:
            continue
        x_positions = [f'{row["batter"]}<br>{row["season"]}' for _, row in season_rows.iterrows()]

    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Blue = actual runs. Orange extension = projected extra runs to reach 16 matches. "
        "Orange bars indicate the batter would have surpassed the actual OC winner on a level playing field."
    )

    beat_count = f["would_have_beaten_oc"].sum()
    st.dataframe(
        f[["season", "batter", "batting_team", "matches", "runs", "runs_per_match",
           "proj_runs_16_matches", "winner", "oc_winner_runs", "would_have_beaten_oc"]]
        .rename(columns={
            "runs_per_match": "Runs/Match",
            "proj_runs_16_matches": "Projected (16 matches)",
            "oc_winner_runs": "OC Winner Runs",
            "would_have_beaten_oc": "Would Beat OC Winner?",
        })
        .sort_values("season"),
        use_container_width=True,
        hide_index=True,
    )

    st.info(
        f"**Finding:** In **{beat_count}** of 23 cases, a non-playoff elite batter would have "
        "surpassed the actual Orange Cap winner if they'd played the same number of matches. "
        "Crucially, their runs-per-match is comparable — the gap is opportunity, not ability "
        "(Mann-Whitney U, p = 0.95, no significant runs difference)."
    )

st.divider()
st.caption(
    "Data: Cricsheet IPL ball-by-ball data (2008–2025), 278,034 deliveries across 1,169 matches. "
    "All statistical tests: p < 0.001 unless noted. Analysis by Sandheep Sridar."
)
