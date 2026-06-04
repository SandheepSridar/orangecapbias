import os
import streamlit as st
import pandas as pd
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


DATA_FILES = {
    "a":  BASE / "analysis_a_winner_positions.csv",
    "b":  BASE / "analysis_b_balls_faced_by_position.csv",
    "c":  BASE / "analysis_c_powerplay_concentration.csv",
    "d":  BASE / "analysis_d_normalised_rankings.csv",
    "e":  BASE / "analysis_e_playoff_match_advantage.csv",
    "f":  BASE / "analysis_f_non_playoff_elite.csv",
    "bs": BASE / "batter_season.csv",
    "oc": Path("data/reference/orange_cap_winners.csv"),
    "moi_best": BASE / "middle_order_index_best.csv",
    "moi_all":  BASE / "middle_order_index_all.csv",
}


# data_version (file mtimes) is part of the cache key, so the cache invalidates
# automatically whenever any source CSV is regenerated.
@st.cache_data
def load_data(data_version):
    return {k: pd.read_csv(p) for k, p in DATA_FILES.items()}


d = load_data(tuple(os.path.getmtime(p) for p in DATA_FILES.values()))

# Actual Orange Cap winner per season = highest *full-season* run-scorer (incl.
# playoffs), which is how the award is decided. batter_season holds full-season
# totals keyed by cricsheet name, so this joins cleanly to every chart below.
GOLD = "#FFC300"
OC_WINNERS = d["bs"].loc[d["bs"].groupby("season")["runs"].idxmax()].set_index("season")

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🏏 IPL Orange Cap: A Structural Bias Analysis")
st.markdown(
    """
    The IPL Orange Cap goes to the highest run-scorer each season.
    This analysis asks: **is that fair?** Ball-by-ball data from all 19 complete
    IPL seasons (2008–2026) shows the award structurally disadvantages middle-order
    batsmen and players on non-playoff teams — not due to skill, but due to design.
    """
)

st.divider()

# ── Key callouts ──────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Seasons Analysed", "19", "2008 – 2026")
c2.metric("Opener/Top-3 Winners", "19 / 19", "100% of all time")
c3.metric("Extra Balls (Openers vs Middle)", "+71 / season", "median, p < 0.001")
c4.metric("Non-Playoff Elite Cases", "23", "top-5 despite fewer matches")

st.divider()

ANALYSES = [
    "A · Winner Positions",
    "B · Balls Faced",
    "C · Powerplay Access",
    "D · Normalised Rankings",
    "E · Playoff Advantage",
    "F · Non-Playoff Elites",
    "G · Best Middle Order",
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
    fig.update_layout(showlegend=False, yaxis_range=[0, 19])
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Season-by-season breakdown**")
    a_display = a[["season", "winner", "team", "total_runs", "avg_batting_position", "position_group", "playoff_team"]]
    st.dataframe(a_display, use_container_width=True, hide_index=True)

    _latest = OC_WINNERS.sort_index().iloc[-1]
    st.caption(
        f"🏆 Every bar and row here is an actual Orange Cap winner. "
        f"Most recent: **{_latest.name}** — {_latest['batter']} "
        f"({int(_latest['runs'])} runs, {int(_latest['matches'])} matches, {_latest['position_group']})."
    )

    st.info(
        "**Finding:** 17 out of 19 winners (89%) batted at positions 1–2. "
        "The remaining 2 (Uthappa 2014, Williamson 2018) batted at position 3. No middle-order or finisher has ever won."
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
    fig.update_traces(showlegend=False)

    w = OC_WINNERS.reset_index()
    w = w[w["position_group"].isin(POSITION_ORDER)]
    fig.add_trace(go.Scatter(
        x=w["position_group"], y=w["balls_faced"],
        mode="markers",
        marker=dict(symbol="star", size=13, color=GOLD, line=dict(color="#7a5c00", width=1)),
        name="🏆 Orange Cap winner",
        customdata=w[["batter", "season", "runs"]].values,
        hovertemplate=(
            "🏆 <b>%{customdata[0]}</b> (%{customdata[1]})<br>"
            "Balls faced: %{y}<br>Season runs: %{customdata[2]}<extra></extra>"
        ),
    ))
    fig.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("🏆 Gold stars mark each season's actual Orange Cap winner — they cluster at the top of the opener distribution.")

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
        "**Finding:** Openers face a median of 71 more balls per season than middle-order batsmen. "
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
    fig.update_layout(yaxis_range=[0, 115])

    # Use analysis_a's position_group (the paper's classification) so these counts
    # match Tab A's narrative exactly (17 openers / 2 top-order).
    win_counts = d["a"]["position_group"].value_counts()
    for grp in POSITION_ORDER:
        n = int(win_counts.get(grp, 0))
        if n:
            fig.add_annotation(
                x=grp, y=107, text=f"🏆 ×{n}", showarrow=False,
                font=dict(size=13, color=GOLD),
            )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "🏆 markers show how many of the 19 Orange Cap winners batted in each group — "
        "all of them in the two leftmost (powerplay-rich) groups. The phase mix above is *why*."
    )

    st.info(
        "**Finding:** Openers score **57.1%** of their seasonal runs in the powerplay (overs 1–6). "
        "Middle-order batsmen score just **17.3%** there — most of them never bat in the powerplay at all. "
        "Powerplay conditions (fielding restrictions, fresh pitch) are systematically unavailable to them."
    )


# ── Tab D — Normalised Rankings ───────────────────────────────────────────────
elif tab == "D · Normalised Rankings":
    st.subheader("When you normalise for matches played, rankings change significantly.")
    st.caption(
        "Projection rule: only **non-playoff** players are scaled up to a full 14-match league season — "
        "they were *structurally denied* matches. Players who reached the playoffs are **not** projected up "
        "for league games they personally missed (e.g. injury), since they already had compensating matches. "
        "This keeps a player's own absence from being counted against batters who played the full league."
    )

    d_df = d["d"].copy()

    season = st.selectbox("Select season", sorted(d_df["season"].unique()), index=0, key="d_season_select")
    season_df = d_df[d_df["season"] == season].copy()
    top10 = season_df[season_df["actual_rank"] <= 10].copy()

    # Distinct y-positions per side so tied ranks (e.g. two players on equal runs)
    # don't stack on the same row. The genuine tie is still shown in the hover.
    top10 = top10.sort_values(["actual_rank", "normalised_runs"], ascending=[True, False]).reset_index(drop=True)
    top10["y_actual"] = range(1, len(top10) + 1)
    norm_order = top10.sort_values(["norm_rank", "league_runs"], ascending=[True, False]).index
    top10.loc[norm_order, "y_norm"] = range(1, len(top10) + 1)

    winner_name = OC_WINNERS.loc[season, "batter"] if season in OC_WINNERS.index else None
    winner_total = int(OC_WINNERS.loc[season, "runs"]) if season in OC_WINNERS.index else None

    fig = go.Figure()
    for _, row in top10.iterrows():
        is_winner = row["batter"] == winner_name
        if is_winner:
            color, width, msize, label = GOLD, 4, 13, f'🏆 {row["batter"]}'
        else:
            color = "#e07b39" if row["y_actual"] != row["y_norm"] else "#adb5bd"
            width, msize, label = 2, 8, row["batter"]
        fig.add_trace(go.Scatter(
            x=[0, 1],
            y=[row["y_actual"], row["y_norm"]],
            mode="lines+markers+text",
            line=dict(color=color, width=width),
            marker=dict(size=msize, color=color, symbol="star" if is_winner else "circle"),
            text=[f'{label} ({int(row["league_runs"])})',
                  f'{label} ({int(row["normalised_runs"])})'],
            textposition=["middle left", "middle right"],
            showlegend=False,
            hovertemplate=(
                f"<b>{row['batter']}</b>"
                + (f" — 🏆 Orange Cap winner ({winner_total} full-season runs)" if is_winner else "")
                + "<br>"
                f"Actual: #{int(row['actual_rank'])} ({int(row['league_runs'])} league runs, {int(row['league_matches'])} matches)<br>"
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
    st.caption("🏆 Gold = the actual Orange Cap winner. Orange = rank changed after normalisation. Grey = rank unchanged.")

    if winner_name is not None:
        if winner_name in set(top10["batter"]):
            wrow = top10[top10["batter"] == winner_name].iloc[0]
            if int(wrow["actual_rank"]) != 1:
                st.warning(
                    f"🏆 **{winner_name}** won the {season} Orange Cap with **{winner_total} full-season runs**, "
                    f"but ranks only **#{int(wrow['actual_rank'])} on league runs** ({int(wrow['league_runs'])}). "
                    "The extra playoff matches — not league output — decided the award."
                )
        else:
            st.warning(
                f"🏆 **{winner_name}** won the {season} Orange Cap with **{winner_total} full-season runs**, "
                "yet doesn't even appear in the league-stage top 10 — the award was driven entirely by playoff matches."
            )

    shift_pct = (d_df[d_df["actual_rank"] <= 10]["actual_rank"] != d_df[d_df["actual_rank"] <= 10]["norm_rank"]).mean() * 100
    st.info(
        f"**Finding:** Across all 19 seasons, **{shift_pct:.1f}%** of top-10 batters have a different "
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
    fig.update_traces(showlegend=False)

    w = OC_WINNERS.reset_index()
    w["Playoff Status"] = w["made_playoffs"].map({1: "Playoff Team", 0: "Non-Playoff Team"})
    fig.add_trace(go.Scatter(
        x=w["Playoff Status"], y=w["matches"],
        mode="markers",
        marker=dict(symbol="star", size=13, color=GOLD, line=dict(color="#7a5c00", width=1)),
        name="🏆 Orange Cap winner",
        customdata=w[["batter", "season"]].values,
        hovertemplate="🏆 <b>%{customdata[0]}</b> (%{customdata[1]})<br>Matches: %{y}<extra></extra>",
    ))
    fig.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("🏆 Gold stars mark each Orange Cap winner — almost all sit in the playoff column with the most matches.")

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
        "Orange bars indicate the batter would have surpassed the actual OC winner on a level playing field. "
        "🏆 Hover any bar to see that season's actual Orange Cap winner and the run tally being compared against."
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


# ── Tab G — Best Middle Order ─────────────────────────────────────────────────
elif tab == "G · Best Middle Order":
    st.subheader("The best middle-order batsman the Orange Cap never sees.")
    st.caption(
        "A composite **Best Middle-Order Index**: for each season, every qualifying "
        "middle-order batsman (average position 4–7, 7+ matches) is scored on four "
        "components — **Volume** (runs per innings), **Efficiency** (strike rate), "
        "**Finishing** (death-over strike rate) and **Consistency** (median runs per "
        "innings). Each component is standardised *within the season* (a z-score: how "
        "many standard deviations above the season's middle-order average), and the four "
        "are averaged with equal weight. The season's Orange Cap winner is excluded — "
        "though none has ever batted in the middle order anyway."
    )

    moi_best = d["moi_best"].copy()
    moi_all = d["moi_all"].copy()

    COMP_COLS = ["z_volume", "z_efficiency", "z_finishing", "z_consistency"]
    COMP_LABELS = {
        "z_volume": "Volume (runs/inns)",
        "z_efficiency": "Efficiency (strike rate)",
        "z_finishing": "Finishing (death SR)",
        "z_consistency": "Consistency (median)",
    }

    # ── Headline callouts ────────────────────────────────────────────────────
    win_counts = moi_best["batter"].value_counts()
    repeats = win_counts[win_counts >= 2]
    top_season = moi_best.loc[moi_best["index"].idxmax()]
    g1, g2, g3 = st.columns(3)
    g1.metric("Seasons covered", f"{moi_best['season'].nunique()}", "2008 – 2026")
    g2.metric("Most-crowned (uncrowned!)",
              ", ".join(repeats[repeats == repeats.max()].index.tolist()),
              f"{int(repeats.max())}× each")
    g3.metric("Most dominant season",
              f"{top_season['batter']} ({int(top_season['season'])})",
              f"index {top_season['index']:.2f}")

    st.divider()

    # ── Season selector → ranking + winner breakdown ─────────────────────────
    season = st.selectbox("Select season", sorted(moi_all["season"].unique()),
                          index=int(moi_all["season"].nunique() - 1), key="moi_season")
    sdf = moi_all[moi_all["season"] == season].sort_values("index", ascending=False)
    topn = sdf.head(8).copy()
    winner = topn.iloc[0]

    left, right = st.columns([3, 2])

    with left:
        st.markdown(f"**Top middle-order batsmen — {season}**")
        bar_colors = [GOLD if i == 0 else "#3a86ff" for i in range(len(topn))]
        fig = go.Figure(go.Bar(
            x=topn["index"], y=topn["batter"], orientation="h",
            marker_color=bar_colors,
            customdata=topn[["team", "avg_pos", "matches", "runs", "sr", "death_sr"]].values,
            hovertemplate=(
                "<b>%{y}</b> — %{customdata[0]}<br>"
                "Index: %{x:.2f}<br>Avg position: %{customdata[1]:.1f}<br>"
                "Matches: %{customdata[2]} · Runs: %{customdata[3]}<br>"
                "Strike rate: %{customdata[4]:.1f} · Death SR: %{customdata[5]:.1f}"
                "<extra></extra>"
            ),
        ))
        fig.update_layout(
            xaxis_title="Best Middle-Order Index", yaxis_title="",
            yaxis=dict(categoryorder="total ascending"),
            height=360, margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("🥇 Gold = the season's top middle-order batsman.")

    with right:
        st.markdown(f"**Why {winner['batter']} won — component z-scores**")
        comp = pd.DataFrame({
            "Component": [COMP_LABELS[c] for c in COMP_COLS],
            "z": [winner[c] for c in COMP_COLS],
        })
        comp_colors = ["#e07b39" if v >= 0 else "#adb5bd" for v in comp["z"]]
        fig_c = go.Figure(go.Bar(
            x=comp["z"], y=comp["Component"], orientation="h",
            marker_color=comp_colors,
            text=[f"{v:+.2f}" for v in comp["z"]], textposition="outside",
        ))
        fig_c.add_vline(x=0, line_color="#333", line_width=1)
        fig_c.update_layout(
            xaxis_title="z-score (vs season's middle order)", yaxis_title="",
            height=360, margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_c, use_container_width=True)
        st.caption("Each bar = how far above (orange) or below (grey) the season's "
                   "middle-order average this player ranked on that skill.")

    st.divider()

    # ── Full leaderboard table ───────────────────────────────────────────────
    st.markdown("**Best middle-order batsman, every season (2008–2026)**")
    show = moi_best[["season", "batter", "team", "avg_pos", "matches", "runs",
                     "sr", "death_sr", "index"]].rename(columns={
        "avg_pos": "Avg Pos", "sr": "Strike Rate", "death_sr": "Death SR", "index": "Index"})
    st.dataframe(show, use_container_width=True, hide_index=True)

    # ── Recurring winners ────────────────────────────────────────────────────
    st.markdown("**The uncrowned regulars** — players who top the index most often")
    rc = win_counts[win_counts >= 2].sort_values()
    fig_r = go.Figure(go.Bar(
        x=rc.values, y=rc.index, orientation="h", marker_color="#3a86ff",
        text=[f"{v}×" for v in rc.values], textposition="outside",
    ))
    fig_r.update_layout(xaxis_title="Seasons as best middle-order batsman", yaxis_title="",
                        height=260, margin=dict(l=10, r=10, t=10, b=10),
                        xaxis=dict(dtick=1))
    st.plotly_chart(fig_r, use_container_width=True)

    st.divider()

    # ── Crowned vs uncrowned: strike rate dumbbell ───────────────────────────
    st.markdown("**Crowned vs uncrowned — who actually struck faster?**")
    oc_sr = OC_WINNERS.reset_index()[["season", "batter", "runs", "balls_faced"]].copy()
    oc_sr["oc_sr"] = oc_sr["runs"] / oc_sr["balls_faced"] * 100
    dumb = (oc_sr.rename(columns={"batter": "oc_name"})
            .merge(moi_best[["season", "batter", "sr"]].rename(
                columns={"batter": "mo_name", "sr": "mo_sr"}), on="season")
            .sort_values("season"))

    fig_d = go.Figure()
    for _, r in dumb.iterrows():
        fig_d.add_trace(go.Scatter(
            x=[r["oc_sr"], r["mo_sr"]], y=[r["season"], r["season"]],
            mode="lines", line=dict(color="#d3d3d3", width=2),
            showlegend=False, hoverinfo="skip"))
    fig_d.add_trace(go.Scatter(
        x=dumb["oc_sr"], y=dumb["season"], mode="markers",
        marker=dict(color="#e07b39", size=10, line=dict(color="#7a4a1f", width=1)),
        name="🏆 Orange Cap winner", customdata=dumb[["oc_name"]].values,
        hovertemplate="🏆 <b>%{customdata[0]}</b> (%{y})<br>Strike rate %{x:.1f}<extra></extra>"))
    fig_d.add_trace(go.Scatter(
        x=dumb["mo_sr"], y=dumb["season"], mode="markers",
        marker=dict(color="#3a86ff", size=10, line=dict(color="#1c4f9c", width=1)),
        name="Best middle-order batsman", customdata=dumb[["mo_name"]].values,
        hovertemplate="<b>%{customdata[0]}</b> (%{y})<br>Strike rate %{x:.1f}<extra></extra>"))
    fig_d.update_layout(
        xaxis_title="Season strike rate", yaxis_title="",
        yaxis=dict(dtick=1, autorange="reversed"),
        height=560, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    st.plotly_chart(fig_d, use_container_width=True)

    faster = int((dumb["mo_sr"] > dumb["oc_sr"]).sum())
    gap = (dumb["mo_sr"] - dumb["oc_sr"]).mean()
    st.caption(
        f"Orange (left) = the season's Orange Cap winner; blue (right) = the best "
        f"middle-order batsman. In **{faster} of {len(dumb)}** seasons the middle-order "
        f"batsman struck faster — by an average of **{gap:.0f} runs per 100 balls**. "
        "The two exceptions are themselves explosive openers (Gayle 2011, Suryavanshi 2026)."
    )

    st.info(
        "**Finding:** The middle order's best are explosive finishers — de Villiers, "
        "Klaasen, Russell, Maxwell, Dhoni, Miller — who strike fast and finish innings "
        "but never accumulate the raw volume an opener does. The Orange Cap, measuring "
        "only aggregate runs, has never recognised a single one of them. An award built "
        "on rate and finishing, not volume, would tell a completely different story."
    )

st.divider()
st.caption(
    "Data: Cricsheet IPL ball-by-ball data (2008–2026), 295,557 deliveries across 1,243 matches. "
    "All statistical tests: p < 0.001 unless noted. Analysis by Sandheep Sridar."
)
