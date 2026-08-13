"""TNPL mirror of the IPL Orange Cap bias Streamlit dashboard (app.py).

TNPL's equivalent of the Orange Cap is the Most Runs award. Same seven
analysis tabs; thresholds rescaled for the 7-match league (4+ matches to
qualify, normalisation to the league length, projection to 9 matches).

Run from the repo root:  streamlit run TNPL/app.py
"""

import os
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="TNPL Most Runs Bias",
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

BASE = Path(__file__).resolve().parent / "tables"
LEAGUE_LEN = 7      # TNPL league stage matches per team
PROJ_MATCHES = 9    # Analysis F projection (league + 2, mirroring the IPL's 16)

DATA_FILES = {
    "a":  BASE / "analysis_a_winner_positions.csv",
    "b":  BASE / "analysis_b_balls_faced_by_position.csv",
    "c":  BASE / "analysis_c_powerplay_concentration.csv",
    "d":  BASE / "analysis_d_normalised_rankings.csv",
    "e":  BASE / "analysis_e_playoff_match_advantage.csv",
    "f":  BASE / "analysis_f_non_playoff_elite.csv",
    "bs": BASE / "batter_season.csv",
    "comp": BASE / "middle_order_components.csv",
}

# MOVI threshold controls (Tab G) — defaults match middle_order_index.py
DEFAULT_MIN_MATCHES = 4
DEFAULT_POS_MIN = 4.0
POS_MAX = 7  # upper bound of the middle-order band — fixed
MATCH_OPTIONS = list(range(2, 8))          # league stage is 7 matches
POS_OPTIONS = [3.75, 3.80, 3.85, 3.90, 3.95, 4.00]
COMP_COLS = ["z_volume", "z_efficiency", "z_finishing", "z_consistency"]


# data_version (file mtimes) is part of the cache key, so the cache invalidates
# automatically whenever any source CSV is regenerated.
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


d = load_data(tuple(os.path.getmtime(p) for p in DATA_FILES.values()))

# Actual Most Runs winner per season = highest full-season run-scorer (incl.
# playoffs), which is how the award is decided. Cross-validated against the
# Wikipedia award list in data_quality_all.py.
GOLD = "#FFC300"
OC_WINNERS = d["bs"].loc[d["bs"].groupby("season")["runs"].idxmax()].set_index("season")
N_SEASONS = d["a"]["season"].nunique()

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🏏 TNPL Most Runs Award: A Structural Bias Analysis")
st.markdown(
    """
    The TNPL Most Runs award — the league's Orange Cap — goes to the highest
    run-scorer each season. This analysis asks: **is that fair?** Ball-by-ball
    data from all 9 complete TNPL seasons (2016–2025) shows the award
    structurally favours openers and players on playoff teams — replicating the
    bias documented in the IPL — not due to skill, but due to design.
    """
)

st.divider()

# ── Key callouts ──────────────────────────────────────────────────────────────
a_counts = d["a"]["position_group"].value_counts()
opener_winners = int(a_counts.get("Opener (1-2)", 0) + a_counts.get("Top Order (3)", 0))
c1, c2, c3, c4 = st.columns(4)
c1.metric("Seasons Analysed", f"{N_SEASONS}", "2016 – 2025")
c2.metric("Opener/Top-3 Winners", f"{opener_winners} / {N_SEASONS}", "all from playoff teams")
c3.metric("Extra Balls (Openers vs Middle)", "+48 / season", "median, p < 0.001")
c4.metric("Non-Playoff Elite Cases", f"{len(d['f'])}", "top-5 despite fewer matches")

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
    st.subheader("Who wins the Most Runs award? Mostly the top order.")

    a = d["a"].copy()
    counts = a["position_group"].value_counts().reindex(POSITION_ORDER, fill_value=0).reset_index()
    counts.columns = ["position_group", "winners"]

    fig = px.bar(
        counts,
        x="position_group", y="winners",
        color="position_group",
        color_discrete_map=POSITION_COLORS,
        labels={"position_group": "Batting Position Group", "winners": "Most Runs Award Winners"},
        text="winners",
        category_orders={"position_group": POSITION_ORDER},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=False, yaxis_range=[0, N_SEASONS])
    st.plotly_chart(fig, width="stretch")

    st.markdown("**Season-by-season breakdown**")
    a_display = a[["season", "winner", "team", "total_runs", "avg_batting_position", "position_group", "playoff_team"]]
    st.dataframe(a_display, width="stretch", hide_index=True)

    _latest = OC_WINNERS.sort_index().iloc[-1]
    st.caption(
        f"🏆 Every bar and row here is an actual Most Runs award winner. "
        f"Most recent: **{_latest.name}** — {_latest['batter']} "
        f"({int(_latest['runs'])} runs, {int(_latest['matches'])} matches, {_latest['position_group']})."
    )

    st.info(
        "**Finding:** 7 of 9 winners batted in the top order (positions 1–2), and "
        "all 9 played for playoff teams. Unlike the IPL — where no winner in 19 "
        "seasons averaged below position 3 — TNPL has two middle-order winners "
        "(Sanjay Yadav 2022, Ajitesh 2023): the bias is strong but not absolute "
        "in a 7-match league."
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
        name="🏆 Most Runs winner",
        customdata=w[["batter", "season", "runs"]].values,
        hovertemplate=(
            "🏆 <b>%{customdata[0]}</b> (%{customdata[1]})<br>"
            "Balls faced: %{y}<br>Season runs: %{customdata[2]}<extra></extra>"
        ),
    ))
    fig.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    st.plotly_chart(fig, width="stretch")
    st.caption("🏆 Gold stars mark each season's actual Most Runs winner — they cluster at the top of the opener distribution.")

    b = d["b"].set_index("position_group").reindex(POSITION_ORDER)
    st.markdown("**Summary statistics**")
    st.dataframe(
        b[["avg_balls", "median_balls", "min_balls", "max_balls", "batter_seasons"]].rename(columns={
            "avg_balls": "Mean", "median_balls": "Median",
            "min_balls": "Min", "max_balls": "Max", "batter_seasons": "N (batter-seasons)"
        }),
        width="stretch",
    )

    st.info(
        "**Finding:** Openers face a median of 48 more balls per season than middle-order "
        "batsmen (144 vs 96 — exactly +50%). More balls = more opportunities to accumulate "
        "runs. This is a structural ceiling, not a skill gap."
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
    # match Tab A's narrative exactly (7 openers / 2 middle order).
    win_counts = d["a"]["position_group"].value_counts()
    for grp in POSITION_ORDER:
        n = int(win_counts.get(grp, 0))
        if n:
            fig.add_annotation(
                x=grp, y=107, text=f"🏆 ×{n}", showarrow=False,
                font=dict(size=13, color=GOLD),
            )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "🏆 markers show how many of the 9 Most Runs winners batted in each group. "
        "The phase mix above is *why* the openers dominate."
    )

    st.info(
        "**Finding:** Openers score **59.2%** of their seasonal runs in the powerplay (overs 1–6). "
        "Middle-order batsmen score just **18.0%** there — most of them never bat in the powerplay at all. "
        "Powerplay conditions (fielding restrictions, fresh pitch) are systematically unavailable to them."
    )


# ── Tab D — Normalised Rankings ───────────────────────────────────────────────
elif tab == "D · Normalised Rankings":
    st.subheader("When you normalise for matches played, rankings change significantly.")
    st.caption(
        f"Projection rule: only **non-playoff** players are scaled up to a full {LEAGUE_LEN}-match league season — "
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
                + (f" — 🏆 Most Runs winner ({winner_total} full-season runs)" if is_winner else "")
                + "<br>"
                f"Actual: #{int(row['actual_rank'])} ({int(row['league_runs'])} league runs, {int(row['league_matches'])} matches)<br>"
                f"Normalised: #{int(row['norm_rank'])} ({int(row['normalised_runs']):.0f} runs @ {LEAGUE_LEN} matches)"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        xaxis=dict(
            tickvals=[0, 1],
            ticktext=["Actual Ranking", f"Normalised to {LEAGUE_LEN} matches"],
            range=[-0.4, 1.4],
        ),
        yaxis=dict(autorange="reversed", title="Rank", dtick=1),
        height=500,
    )
    st.plotly_chart(fig, width="stretch")
    st.caption("🏆 Gold = the actual Most Runs winner. Orange = rank changed after normalisation. Grey = rank unchanged.")

    if winner_name is not None:
        if winner_name in set(top10["batter"]):
            wrow = top10[top10["batter"] == winner_name].iloc[0]
            if int(wrow["actual_rank"]) != 1:
                st.warning(
                    f"🏆 **{winner_name}** won the {season} Most Runs award with **{winner_total} full-season runs**, "
                    f"but ranks only **#{int(wrow['actual_rank'])} on league runs** ({int(wrow['league_runs'])}). "
                    "The extra playoff matches — not league output — decided the award."
                )
        else:
            st.warning(
                f"🏆 **{winner_name}** won the {season} Most Runs award with **{winner_total} full-season runs**, "
                "yet doesn't even appear in the league-stage top 10 — the award was driven entirely by playoff matches."
            )

    shift_pct = (d_df[d_df["actual_rank"] <= 10]["actual_rank"] != d_df[d_df["actual_rank"] <= 10]["norm_rank"]).mean() * 100
    st.info(
        f"**Finding:** Across all {N_SEASONS} seasons, **{shift_pct:.1f}%** of top-10 batters have a different "
        f"rank after normalising to a standard {LEAGUE_LEN}-match league season (Wilcoxon signed-rank, p = 0.037). "
        "In 3 of 9 seasons (2016, 2019, 2022) the actual run leader loses the top spot."
    )

    # ── Confidence interval chart (only for batters with missing matches) ─────
    projected = season_df[season_df["missing_matches"] > 0].copy()
    if not projected.empty:
        st.markdown(f"#### Projection uncertainty for batters with fewer than {LEAGUE_LEN} league matches")

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
                f"Matches played: %{{customdata[2]}} of {LEAGUE_LEN}"
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
            xaxis_title=f"Projected runs (normalised to {LEAGUE_LEN} matches)",
            yaxis_title="",
            height=max(250, len(projected) * 55),
            margin=dict(l=140),
        )
        st.plotly_chart(fig_ci, width="stretch")
        st.caption(
            f"Dots = projected {LEAGUE_LEN}-match total. Bars = 95% confidence interval. "
            "Orange dashed line = actual season #1's run tally. "
            "Batters whose CI bar crosses the orange line had a plausible path to the award."
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
        name="🏆 Most Runs winner",
        customdata=w[["batter", "season"]].values,
        hovertemplate="🏆 <b>%{customdata[0]}</b> (%{customdata[1]})<br>Matches: %{y}<extra></extra>",
    ))
    fig.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    st.plotly_chart(fig, width="stretch")
    st.caption("🏆 Gold stars mark each Most Runs winner — every single one sits in the playoff column.")

    st.info(
        f"**Finding:** Playoff teams play a median of **{playoff_med:.0f} matches** vs "
        f"**{non_playoff_med:.0f}** for non-playoff teams (Mann-Whitney U, p < 0.001). "
        "At ~40 runs per match, that's roughly **80 free runs** just for qualifying — "
        "and all 9 Most Runs winners came from playoff teams."
    )


# ── Tab F — Non-Playoff Elites ────────────────────────────────────────────────
elif tab == "F · Non-Playoff Elites":
    st.subheader("Non-playoff batsmen match elite output — with fewer matches.")

    f = d["f"].copy()
    a = d["a"].copy()

    f = f.merge(a[["season", "winner", "total_runs"]], on="season", how="left")
    f = f.rename(columns={"total_runs": "oc_winner_runs"})
    proj_col = f"proj_runs_{PROJ_MATCHES}_matches"

    f["would_have_beaten_oc"] = f[proj_col] > f["oc_winner_runs"]

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
                f"Projected ({PROJ_MATCHES} matches): {row[proj_col]}<br>"
                f"Most Runs winner that year: {row['winner']} ({row['oc_winner_runs']} runs)"
                "<extra></extra>"
            ),
        ))
        fig.add_trace(go.Bar(
            x=[f'{row["batter"]}<br>{row["season"]}'],
            y=[row[proj_col] - row["runs"]],
            marker_color=color,
            showlegend=False,
            hovertemplate=(
                f"Projected extra runs (to {PROJ_MATCHES} matches): +{row[proj_col] - row['runs']:.0f}"
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
    st.plotly_chart(fig, width="stretch")
    st.caption(
        f"Blue = actual runs. Orange extension = projected extra runs to reach {PROJ_MATCHES} matches. "
        "Orange bars indicate the batter would have surpassed the actual Most Runs winner on a level playing field. "
        "🏆 Hover any bar to see that season's actual winner and the run tally being compared against."
    )

    beat_count = int(f["would_have_beaten_oc"].sum())
    st.dataframe(
        f[["season", "batter", "batting_team", "matches", "runs", "runs_per_match",
           proj_col, "winner", "oc_winner_runs", "would_have_beaten_oc"]]
        .rename(columns={
            "runs_per_match": "Runs/Match",
            proj_col: f"Projected ({PROJ_MATCHES} matches)",
            "oc_winner_runs": "Winner Runs",
            "would_have_beaten_oc": "Would Beat Winner?",
        })
        .sort_values("season"),
        width="stretch",
        hide_index=True,
    )

    st.info(
        f"**Finding:** In **{beat_count}** of {len(f)} cases, a non-playoff elite batter would have "
        "surpassed the actual Most Runs winner if they'd played the same number of matches. "
        "The starkest: Murali Vijay 2019 — 359 runs in just 4 matches (~90/match) for non-playoff "
        "Trichy. And 2023's non-playoff #2 is Sai Sudharsan — who won the actual IPL Orange Cap in 2025."
    )


# ── Tab G — Best Middle Order ─────────────────────────────────────────────────
elif tab == "G · Best Middle Order":
    st.subheader("The best middle-order batsman the Most Runs award never sees.")
    st.caption(
        "A composite **Best Middle-Order Index** (MOVI): for each season, every qualifying "
        "middle-order batsman (average position 4–7, 4+ matches) is scored on four "
        "components — **Volume** (runs per innings), **Efficiency** (strike rate), "
        "**Finishing** (death-over strike rate) and **Consistency** (median runs per "
        "innings). Each component is standardised *within the season* (a z-score: how "
        "many standard deviations above the season's middle-order average), and the four "
        "are averaged with equal weight."
    )

    # ── Threshold controls (live recompute, as in app_movi.py) ───────────────
    min_matches = st.segmented_control(
        "Minimum matches to qualify in a season", options=MATCH_OPTIONS,
        default=DEFAULT_MIN_MATCHES, key="movi_minmatches",
        help="MOVI is recomputed live. A higher bar removes small-sample seasons; a "
             "lower bar lets in players who featured in fewer games.")
    min_matches = DEFAULT_MIN_MATCHES if min_matches is None else min_matches
    st.caption(f"💡 Suggested: keep this at **{DEFAULT_MIN_MATCHES}** — about half the "
               f"{LEAGUE_LEN}-match league stage (the IPL study's 7-of-14 bar), so short "
               "cameo bursts aren't over-weighted against players who batted a full season.")
    pos_min = st.segmented_control(
        "Lowest average batting position to include", options=POS_OPTIONS,
        default=DEFAULT_POS_MIN, format_func=lambda x: f"{x:.2f}", key="movi_posmin",
        help=f"The middle-order band is [this value, {POS_MAX}]. The upper bound is "
             f"fixed at {POS_MAX}. Lowering this admits batsmen who average just below "
             "4 (floating No. 3–4s).")
    pos_min = DEFAULT_POS_MIN if pos_min is None else pos_min
    st.caption("💡 Suggested: keep this at **4** — that isolates *true* middle-order "
               "batsmen. Lower values let in floating No. 3–4s, which dilutes the group.")

    moi_all = compute_movi(d["comp"], min_matches, pos_min)
    moi_best = moi_all[moi_all["season_rank"] == 1].sort_values("season")
    if min_matches != DEFAULT_MIN_MATCHES or pos_min != DEFAULT_POS_MIN:
        st.caption(f"Showing MOVI for positions **{pos_min:g}–{POS_MAX}** at a "
                   f"**{min_matches}-match** minimum "
                   f"(defaults: {DEFAULT_POS_MIN:g}–{POS_MAX}, {DEFAULT_MIN_MATCHES} matches).")
    if moi_best.empty:
        st.warning("No batter-season qualifies at these thresholds — relax them to continue.")
        st.stop()

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
    g1.metric("Seasons covered", f"{moi_best['season'].nunique()}", "2016 – 2025")
    g2.metric("Most-crowned (uncrowned!)",
              ", ".join(repeats[repeats == repeats.max()].index.tolist()) if not repeats.empty else "—",
              f"{int(repeats.max())}× each" if not repeats.empty else "no repeats")
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
        st.plotly_chart(fig, width="stretch")
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
        st.plotly_chart(fig_c, width="stretch")
        st.caption("Each bar = how far above (orange) or below (grey) the season's "
                   "middle-order average this player ranked on that skill.")

    st.divider()

    # ── Full leaderboard table ───────────────────────────────────────────────
    st.markdown("**Best middle-order batsman, every season (2016–2025)**")
    show = moi_best[["season", "batter", "team", "avg_pos", "matches", "runs",
                     "sr", "death_sr", "index"]].round(
        {"avg_pos": 2, "sr": 1, "death_sr": 1, "index": 2}).rename(columns={
        "avg_pos": "Avg Pos", "sr": "Strike Rate", "death_sr": "Death SR", "index": "Index"})
    st.dataframe(show, width="stretch", hide_index=True)

    # ── Recurring winners ────────────────────────────────────────────────────
    if not repeats.empty:
        st.markdown("**The uncrowned regulars** — players who top the index most often")
        rc = repeats.sort_values()
        fig_r = go.Figure(go.Bar(
            x=rc.values, y=rc.index, orientation="h", marker_color="#3a86ff",
            text=[f"{v}×" for v in rc.values], textposition="outside",
        ))
        fig_r.update_layout(xaxis_title="Seasons as best middle-order batsman", yaxis_title="",
                            height=260, margin=dict(l=10, r=10, t=10, b=10),
                            xaxis=dict(dtick=1))
        st.plotly_chart(fig_r, width="stretch")

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
        name="🏆 Most Runs winner", customdata=dumb[["oc_name"]].values,
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
    st.plotly_chart(fig_d, width="stretch")

    faster = int((dumb["mo_sr"] > dumb["oc_sr"]).sum())
    gap = (dumb["mo_sr"] - dumb["oc_sr"]).mean()
    st.caption(
        f"Orange = the season's Most Runs winner; blue = the best middle-order batsman. "
        f"In **{faster} of {len(dumb)}** seasons the middle-order batsman struck faster — "
        f"by an average of **{gap:.0f} runs per 100 balls**. In 2022 the two dots nearly "
        "overlap because they are the same player: Sanjay Yadav won the Most Runs award "
        "*from No. 4* and tops the index that season."
    )

    st.info(
        "**Finding:** At the standard thresholds, TNPL's best middle-order batsmen — "
        "Shahrukh Khan (3× index leader), Rajagopal Sathish (2×) — strike far faster "
        "than the run leaders but never accumulate opener volume. In 7 of 9 seasons "
        "the index leader won no individual TNPL award. An award built on rate and "
        "finishing, not volume, would tell a completely different story."
    )

st.divider()
st.caption(
    "Data: ESPNcricinfo ball-by-ball data via ESPN core API (2016–2025), 66,534 deliveries "
    "across 285 TNPL matches. Validation: all innings totals reconcile with official scores; "
    "every season's run leader matches the league's Most Runs award. Analysis by Sandheep Sridar."
)
