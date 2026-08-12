"""Build data.js for the NJSBCL competition-analysis dashboard.

Reads the scraped CSVs/schedule exports in ../data/ and precomputes everything
the dashboard needs per opponent team: top batsmen/bowlers, dismissal
breakdowns, toss advice, head-to-head vs our team, and upcoming fixtures.
Mirrors the website/build_data.py -> data.js pattern used for MOVI.

Usage: source ../.venv/bin/activate && python3 build_data.py
"""
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_FILE = Path(__file__).parent / "data.js"
TODAY = datetime(2026, 8, 11)

SERIES = {
    "division1": {
        "label": "2026 Division 1",
        "gladiators": "Samudhra Gladiators",
        "bat_csv": "division1_scorecards_batting.csv",
        "bowl_csv": "division1_scorecards_bowling.csv",
        "schedule_xlsx": "division1_schedule.xlsx",
        "totals_csv": "division1_true_totals.csv",
        "points_csv": "division1_points_table.csv",
        "overs_csv": "division1_gladiators_overs.csv",
    },
    "weekenders": {
        "label": "2026 Weekenders Cup",
        "gladiators": "VRK Gladiators",
        "bat_csv": "weekenderscup_scorecards_batting.csv",
        "bowl_csv": "weekenderscup_scorecards_bowling.csv",
        "schedule_xlsx": "weekenderscup_schedule.xlsx",
        "totals_csv": "weekenderscup_true_totals.csv",
        "points_csv": "weekenderscup_points_table.csv",
        "overs_csv": "weekenderscup_gladiators_overs.csv",
    },
}

ELO_START = 1500
ELO_K = 32
MIN_OVERS_FOR_WEAKNESS = 8
MIN_DEATH_OVERS = 3


def clean_name(n):
    if pd.isna(n):
        return ""
    n = re.sub(r"[*†]", "", str(n)).strip()
    return re.sub(r"\s+", " ", n)


def abbrev(full):
    words = full.split(" ")
    if len(words) == 1:
        return full
    return " ".join(words[:-1]) + " " + words[-1][0]


def parse_dismissal(raw):
    """Returns (type, bowler_raw_abbrev_or_None)."""
    if pd.isna(raw):
        return (None, None)
    s = str(raw).strip()
    low = s.lower()
    if low == "not out":
        return (None, None)
    if low.startswith("run out"):
        return ("Run Out", None)
    if low.startswith("retired"):
        return ("Retired", None)
    if low.startswith("hit wicket"):
        return ("Hit Wicket", s[len("Hit Wicket"):].strip() or None)
    if low.startswith("handled"):
        return ("Handled Ball", None)
    if low.startswith("c&b") or low.startswith("c &b"):
        m = re.match(r"c\s*&\s*b\s+(.*)", s, re.IGNORECASE)
        return ("Caught & Bowled", m.group(1).strip() if m else None)
    if low.startswith("lbw"):
        parts = s.rsplit(" b ", 1)
        return ("LBW", parts[1].strip() if len(parts) == 2 else None)
    if low.startswith("st ") or low.startswith("st."):
        parts = s.rsplit(" b ", 1)
        return ("Stumped", parts[1].strip() if len(parts) == 2 else None)
    if low.startswith("c ") or low.startswith("c†") or s.startswith("c\xa0"):
        parts = s.rsplit(" b ", 1)
        return ("Caught", parts[1].strip() if len(parts) == 2 else None)
    if low.startswith("b "):
        return ("Bowled", s[2:].strip())
    return ("Other", None)


def overs_to_balls(o):
    if pd.isna(o):
        return 0
    whole = int(o)
    frac = round((float(o) - whole) * 10)
    return whole * 6 + frac


def balls_to_overs_str(b):
    return f"{b // 6}.{b % 6}"


def build_abbrev_map(bowl):
    """(team, abbrev-or-full lowercased) -> clean full bowler name, built from the
    complete scorecards_bowling roster. Used to resolve short forms like "Vinit B"
    seen in dismissal text and over-by-over tables back to a canonical full name."""
    abbrev_map = {}
    for _, row in bowl.iterrows():
        full = row["bowlerClean"]
        if not full:
            continue
        abbrev_map[(row["team"], abbrev(full).lower())] = full
        abbrev_map[(row["team"], full.lower())] = full
    return abbrev_map


def load_series(key, cfg):
    bat = pd.read_csv(DATA_DIR / cfg["bat_csv"])
    bowl = pd.read_csv(DATA_DIR / cfg["bowl_csv"])
    bat["team"] = bat["team"].str.strip()
    bowl["team"] = bowl["team"].str.strip()
    bat["playerClean"] = bat["player"].apply(clean_name)
    bowl["bowlerClean"] = bowl["bowler"].apply(clean_name)

    dtypes = bat["dismissal"].apply(parse_dismissal)
    bat["dtype"] = dtypes.apply(lambda x: x[0])
    bat["dbowlerRaw"] = dtypes.apply(lambda x: x[1])

    abbrev_map = build_abbrev_map(bowl)

    teams_per_match = bat.groupby("matchId")["team"].unique().to_dict()

    def resolve_bowler(row):
        if pd.isna(row["dbowlerRaw"]):
            return None
        others = [t for t in teams_per_match[row["matchId"]] if t != row["team"]]
        if not others:
            return None
        return abbrev_map.get((others[0], str(row["dbowlerRaw"]).strip().lower()))

    bat["bowlerResolved"] = bat.apply(resolve_bowler, axis=1)

    # True final scores (batter-runs sum excludes extras, which are large enough in
    # this league — 10-20 runs/innings — to flip real results). listMatches.do embeds
    # the official score1/score2 in batting order, which we use instead.
    totals = pd.read_csv(DATA_DIR / cfg["totals_csv"])
    totals_map = {
        int(r["matchId"]): (int(r["score1"]), int(r["score2"]))
        for _, r in totals.iterrows()
    }

    # team order per match (first team encountered in scorecards == batted first,
    # matching the order score1/score2 are listed in on listMatches.do)
    team_order_2 = {}
    for match_id, grp in bat.groupby("matchId"):
        teams_seen = list(dict.fromkeys(grp["team"]))
        if len(teams_seen) == 2:
            team_order_2[match_id] = teams_seen

    match_rows = []
    skipped = 0
    for match_id, teams in team_order_2.items():
        if match_id not in totals_map:
            skipped += 1
            continue
        team1, team2 = teams
        score1, score2 = totals_map[match_id]
        if score1 == score2:
            res1, res2 = "Tie", "Tie"
        elif score1 > score2:
            res1, res2 = "Win", "Loss"
        else:
            res1, res2 = "Loss", "Win"
        match_rows.append({
            "matchId": match_id, "team": team1, "opponent": team2,
            "teamScore": score1, "oppScore": score2,
            "battedFirst": True, "result": res1,
        })
        match_rows.append({
            "matchId": match_id, "team": team2, "opponent": team1,
            "teamScore": score2, "oppScore": score1,
            "battedFirst": False, "result": res2,
        })
    if skipped:
        print(f"  WARNING: {skipped} matches had no true-totals row, skipped from results")
    results = pd.DataFrame(match_rows)
    results, venue_stats = attach_venue(results, cfg)

    return bat, bowl, results, abbrev_map, venue_stats


def attach_venue(results, cfg):
    """Adds a 'venue' column ('Home'/'Away') to `results` by matching each completed
    match to a row in the schedule export.

    The schedule and results tables don't share a match ID — schedule only has team
    names + calendar dates, results only has matchId (a chronological proxy). But the
    schedule's `Ground` field is reliably just the hosting team's own name (verified:
    effectively 100% of rows across both series), so if we can line up "which schedule
    row is this specific completed match", Ground tells us who hosted it directly.

    We line them up by team-pair: for each unordered pair of teams, sort that pair's
    schedule rows by date and that pair's completed matches by matchId, then zip them
    positionally. This works because a pair usually meets at most once or twice a
    season (single or double round-robin), so chronological order within the pair is
    almost always unambiguous. Matches that don't resolve (no schedule row for that
    pair, or Ground doesn't match either team name) are left with venue=None rather
    than guessed."""
    sched = pd.read_excel(DATA_DIR / cfg["schedule_xlsx"], header=1)
    sched["parsedDate"] = pd.to_datetime(sched["Date"], format="%m/%d/%Y", errors="coerce")
    sched = sched.dropna(subset=["parsedDate", "Team One", "Team Two", "Ground"])

    sched_by_pair = {}
    for _, r in sched.sort_values("parsedDate").iterrows():
        t1, t2, ground = str(r["Team One"]).strip(), str(r["Team Two"]).strip(), str(r["Ground"]).strip()
        pair = frozenset({t1.lower(), t2.lower()})
        sched_by_pair.setdefault(pair, []).append(ground)

    one_row_per_match = results.drop_duplicates("matchId", keep="first").sort_values("matchId")
    results_by_pair = {}
    for _, r in one_row_per_match.iterrows():
        pair = frozenset({r["team"].lower(), r["opponent"].lower()})
        results_by_pair.setdefault(pair, []).append((r["matchId"], r["team"], r["opponent"]))

    venue_map = {}  # matchId -> {team: "Home"/"Away"}
    matched, no_schedule_row, ground_mismatch = 0, 0, 0
    for pair, matches in results_by_pair.items():
        grounds = sched_by_pair.get(pair, [])
        for i, (match_id, team, opponent) in enumerate(matches):
            if i >= len(grounds):
                no_schedule_row += 1
                continue
            ground_norm = grounds[i].lower()
            if ground_norm == team.lower():
                host = team
            elif ground_norm == opponent.lower():
                host = opponent
            else:
                ground_mismatch += 1
                continue
            venue_map[match_id] = {
                team: ("Home" if host == team else "Away"),
                opponent: ("Home" if host == opponent else "Away"),
            }
            matched += 1

    results = results.copy()
    results["venue"] = results.apply(lambda r: venue_map.get(r["matchId"], {}).get(r["team"]), axis=1)
    stats = {
        "totalMatches": len(one_row_per_match), "matched": matched,
        "noScheduleRow": no_schedule_row, "groundMismatch": ground_mismatch,
    }
    return results, stats


def home_away_record(results, team):
    sub = results[(results["team"] == team) & (results["result"] != "Tie") & results["venue"].notna()]
    home = sub[sub["venue"] == "Home"]
    away = sub[sub["venue"] == "Away"]
    home_wins, away_wins = int((home["result"] == "Win").sum()), int((away["result"] == "Win").sum())
    home_n, away_n = len(home), len(away)
    return {
        "home": {"matches": home_n, "wins": home_wins,
                 "winPct": round(100 * home_wins / home_n) if home_n else None},
        "away": {"matches": away_n, "wins": away_wins,
                 "winPct": round(100 * away_wins / away_n) if away_n else None},
    }


def team_batting_agg(bat, team):
    sub = bat[bat["team"] == team].copy()
    grp = sub.groupby("playerClean")
    rows = []
    for player, g in grp:
        innings = len(g)
        notouts = (g["dtype"].isna()).sum()
        outs = innings - notouts
        runs = int(g["R"].sum())
        balls = int(g["B"].sum())
        avg = round(runs / outs, 1) if outs > 0 else runs
        sr = round(100 * runs / balls, 1) if balls > 0 else 0
        rows.append({
            "player": player, "innings": innings, "runs": runs, "balls": balls,
            "notouts": int(notouts), "avg": avg, "sr": sr,
            "hs": int(g["R"].max()), "fours": int(g["4s"].sum()), "sixes": int(g["6s"].sum()),
        })
    return pd.DataFrame(rows).sort_values("runs", ascending=False).reset_index(drop=True)


def recent_form(bat, team, player, n=5, min_innings=3):
    """Last-n-innings batting form vs their own season mean, for a simple hot/cold/steady
    read. Uses matchId order as a chronological proxy — matchIds increase monotonically
    with match date on this site, same assumption compute_elo relies on."""
    sub = bat[(bat["team"] == team) & (bat["playerClean"] == player)].sort_values("matchId")
    if sub.empty:
        return None
    innings = [
        {"runs": int(r["R"]), "notOut": bool(pd.isna(r["dtype"]))}
        for _, r in sub.iterrows()
    ]
    last_n = innings[-n:]
    season_mean = round(sub["R"].mean(), 1)
    last_n_mean = round(sum(x["runs"] for x in last_n) / len(last_n), 1)
    if len(sub) < min_innings or season_mean == 0:
        trend = "insufficient"
    elif last_n_mean / season_mean >= 1.25:
        trend = "hot"
    elif last_n_mean / season_mean <= 0.75:
        trend = "cold"
    else:
        trend = "steady"
    return {
        "innings": last_n, "last5Mean": last_n_mean, "seasonMean": season_mean, "trend": trend,
    }


def detect_collapses(bat, results, team, min_wickets=3, max_runs=20, top_n_positions=7):
    """Finds the worst 'batting collapse' per innings for `team`: the longest run of
    min_wickets+ consecutive dismissals (in scorecard row order, which is batting/arrival
    order) whose combined runs are <= max_runs. This is a proxy — we don't have exact
    over-by-over timing for every match (only for our own team's matches, see
    load_death_overs), so "consecutive dismissed batters' combined runs" stands in for
    "runs added while these wickets fell". Default: 3+ wickets for under 20 combined runs.

    Restricted to the first `top_n_positions` batters (default 7): innings here run up to
    11 batters (median 10), and the last few almost always fold cheaply going for quick
    runs at the end — that's normal tail-wagging, not a "collapse". Verified against real
    data: without this restriction, the league's strongest team (13-2 record) showed a 73%
    collapse rate, and its "worst" instance was batters #5-10 of 11 going cheap *after* the
    top 4 had already put up 92 — restricting to the top order is what makes this metric
    mean what "collapse" actually means."""
    sub = bat[bat["team"] == team]
    opp_lookup = {r["matchId"]: r["opponent"] for _, r in results[results["team"] == team].iterrows()}

    total_innings = 0
    collapse_count = 0
    worst = None
    for match_id, g in sub.groupby("matchId"):
        total_innings += 1
        g = g.head(top_n_positions)
        outs = [int(r["R"]) for _, r in g.iterrows() if pd.notna(r["dtype"]) and r["dtype"] != "Retired"]
        n = len(outs)
        best = None  # (wickets, runs) — most wickets, tie-break fewest runs
        for start in range(n):
            cum = 0
            for end in range(start, n):
                cum += outs[end]
                wkts = end - start + 1
                if wkts >= min_wickets and cum <= max_runs:
                    if best is None or wkts > best[0] or (wkts == best[0] and cum < best[1]):
                        best = (wkts, cum)
        if best is not None:
            collapse_count += 1
            wkts, runs = best
            if worst is None or wkts > worst["wickets"] or (wkts == worst["wickets"] and runs < worst["runs"]):
                worst = {"matchId": int(match_id), "opponent": opp_lookup.get(match_id, "?"),
                         "wickets": wkts, "runs": runs}

    return {
        "totalInnings": total_innings, "collapseCount": collapse_count,
        "collapsePct": round(100 * collapse_count / total_innings) if total_innings else 0,
        "worst": worst,
        "minWickets": min_wickets, "maxRuns": max_runs, "topNPositions": top_n_positions,
    }


def team_bowling_agg(bowl, team):
    sub = bowl[bowl["team"] == team].copy()
    sub["balls"] = sub["O"].apply(overs_to_balls)
    grp = sub.groupby("bowlerClean")
    rows = []
    for player, g in grp:
        wkts = int(g["W"].sum())
        balls = int(g["balls"].sum())
        runs = int(g["R"].sum())
        econ = round(runs / (balls / 6), 2) if balls > 0 else 0
        avg = round(runs / wkts, 1) if wkts > 0 else None
        rows.append({
            "player": player, "wickets": wkts, "overs": balls_to_overs_str(balls),
            "runs": runs, "econ": econ, "avg": avg,
        })
    return pd.DataFrame(rows).sort_values("wickets", ascending=False).reset_index(drop=True)


def bowler_weakness_pool(bowl, min_overs=MIN_OVERS_FOR_WEAKNESS):
    """Per-bowler-per-team season stats used to rank 'weak bowlers to target':
    poor economy, prone to an expensive spell (worst single-match economy), and
    leaks extra runs via wides/no-balls. Z-scored across the whole league (both
    teams' bowlers) so a team's weakest options are judged against the full field,
    not just their own teammates. min_overs filters out small-sample cameos."""
    sub = bowl.copy()
    sub["balls"] = sub["O"].apply(overs_to_balls)
    sub["matchOvers"] = sub["balls"] / 6
    sub["matchEcon"] = sub.apply(
        lambda r: round(r["R"] / r["matchOvers"], 2) if r["matchOvers"] > 0 else 0, axis=1
    )
    rows = []
    for (team, player), g in sub.groupby(["team", "bowlerClean"]):
        total_overs = g["balls"].sum() / 6
        if total_overs < min_overs:
            continue
        runs = int(g["R"].sum())
        econ = round(runs / total_overs, 2)
        worst_row = g.loc[g["matchEcon"].idxmax()]
        # worstEcon (a rate) is used only internally below to pick which match was the
        # worst and to rank bowlers against each other — it is NOT shown to the user as
        # a "runs/over" figure. Extrapolating a 2-3 ball spell up to a per-over rate
        # produces alarming-looking but meaningless numbers (13 runs off 2 legal balls
        # would read as "39/over", which never actually happened). Instead we surface the
        # raw runs conceded and raw balls bowled (legal deliveries + wides + no-balls) in
        # that spell, e.g. "13 runs off 3 balls" — true regardless of spell length.
        worst_econ = round(worst_row["matchEcon"], 2)
        worst_spell_runs = int(worst_row["R"])
        worst_spell_balls = overs_to_balls(worst_row["O"]) + int(worst_row["wides"]) + int(worst_row["noballs"])
        extras = int(g["wides"].sum() + g["noballs"].sum())
        extras_rate = round(extras / total_overs, 2)
        rows.append({
            "team": team, "player": player, "overs": round(total_overs, 1),
            "wickets": int(g["W"].sum()), "econ": econ, "worstEcon": worst_econ,
            "worstSpellRuns": worst_spell_runs, "worstSpellBalls": worst_spell_balls,
            "extras": extras, "extrasRate": extras_rate,
        })
    pool = pd.DataFrame(rows)
    if pool.empty:
        return pool
    for col in ["econ", "worstEcon", "extrasRate"]:
        mean, std = pool[col].mean(), pool[col].std()
        pool[col + "Z"] = (pool[col] - mean) / std if std > 0 else 0.0
    pool["weaknessScore"] = pool[["econZ", "worstEconZ", "extrasRateZ"]].mean(axis=1)
    return pool


def weak_bowlers(pool, team, top_n=3):
    if pool.empty:
        return []
    sub = pool[pool["team"] == team].sort_values("weaknessScore", ascending=False).head(top_n)
    return [
        {
            "player": r["player"], "overs": r["overs"], "wickets": int(r["wickets"]),
            "econ": r["econ"],
            "worstSpellRuns": int(r["worstSpellRuns"]), "worstSpellBalls": int(r["worstSpellBalls"]),
            "extras": int(r["extras"]), "extrasRate": r["extrasRate"],
        }
        for _, r in sub.iterrows()
    ]


def bowler_strength_pool(bowl, min_overs=MIN_OVERS_FOR_WEAKNESS):
    """Per-bowler-per-team season stats highlighting bowling strengths: low economy and a
    high dot-ball rate (building pressure, drying up scoring). Z-scored across the whole
    league so a team's best options are judged against the full field. Mirrors
    bowler_weakness_pool but for the opposite purpose — who to build an attack around,
    rather than who to target."""
    sub = bowl.copy()
    sub["balls"] = sub["O"].apply(overs_to_balls)
    rows = []
    for (team, player), g in sub.groupby(["team", "bowlerClean"]):
        total_balls = int(g["balls"].sum())
        total_overs = total_balls / 6
        if total_overs < min_overs:
            continue
        runs = int(g["R"].sum())
        dots = int(g["Dot"].sum())
        econ = round(runs / total_overs, 2)
        dot_pct = round(100 * dots / total_balls, 1) if total_balls else 0.0
        rows.append({
            "team": team, "player": player, "overs": round(total_overs, 1),
            "wickets": int(g["W"].sum()), "econ": econ, "dotPct": dot_pct,
        })
    pool = pd.DataFrame(rows)
    if pool.empty:
        return pool
    econ_mean, econ_std = pool["econ"].mean(), pool["econ"].std()
    dot_mean, dot_std = pool["dotPct"].mean(), pool["dotPct"].std()
    econ_z = (pool["econ"] - econ_mean) / econ_std if econ_std > 0 else 0.0
    dot_z = (pool["dotPct"] - dot_mean) / dot_std if dot_std > 0 else 0.0
    pool["strengthScore"] = (dot_z - econ_z) / 2  # low econ (negated) + high dot%, equal weight
    return pool


def bowling_strengths(pool, team, top_n=3):
    if pool.empty:
        return []
    sub = pool[pool["team"] == team].sort_values("strengthScore", ascending=False).head(top_n)
    return [
        {
            "player": r["player"], "overs": r["overs"], "wickets": int(r["wickets"]),
            "econ": r["econ"], "dotPct": r["dotPct"],
        }
        for _, r in sub.iterrows()
    ]


MIN_INNINGS_FOR_BAT_STRENGTH = 5


def batter_strength_pool(bat, min_innings=MIN_INNINGS_FOR_BAT_STRENGTH):
    """Per-batter-per-team season stats highlighting batting value: batting average and
    strike rate, z-scored across the whole league (same equal-weight composite pattern as
    bowler_strength_pool) so a player's value is judged against the full field, not just
    their own teammates. min_innings filters out small-sample cameos."""
    rows = []
    for (team, player), g in bat.groupby(["team", "playerClean"]):
        innings = len(g)
        if innings < min_innings:
            continue
        notouts = int(g["dtype"].isna().sum())
        outs = innings - notouts
        runs = int(g["R"].sum())
        balls = int(g["B"].sum())
        avg = round(runs / outs, 1) if outs > 0 else float(runs)
        sr = round(100 * runs / balls, 1) if balls > 0 else 0.0
        rows.append({"team": team, "player": player, "innings": innings, "runs": runs, "avg": avg, "sr": sr})
    pool = pd.DataFrame(rows)
    if pool.empty:
        return pool
    avg_mean, avg_std = pool["avg"].mean(), pool["avg"].std()
    sr_mean, sr_std = pool["sr"].mean(), pool["sr"].std()
    avg_z = (pool["avg"] - avg_mean) / avg_std if avg_std > 0 else 0.0
    sr_z = (pool["sr"] - sr_mean) / sr_std if sr_std > 0 else 0.0
    pool["battingScore"] = (avg_z + sr_z) / 2
    return pool


def best_playing_xi(bat, bat_pool, bowl_pool, team):
    """Suggests a Playing XI from `team`'s full-season squad: the designated wicketkeeper
    (identified from the '†' marker cricclubs uses in the raw scorecard), the best 5
    remaining batting options by battingScore, enough bowling options by strengthScore to
    cover a full attack (aiming for 5 recognized bowlers in the XI), then fills any
    remaining spots with the best leftover combined value. Both scores come from
    league-wide z-scored pools (batter_strength_pool / bowler_strength_pool), so this
    reflects each player's value against the whole league, not just their own teammates."""
    squad_bat = bat_pool[bat_pool["team"] == team].set_index("player") if not bat_pool.empty else bat_pool
    squad_bowl = bowl_pool[bowl_pool["team"] == team].set_index("player") if not bowl_pool.empty else bowl_pool

    wk_rows = bat[(bat["team"] == team) & (bat["player"].str.contains("†", na=False))]
    keeper = wk_rows["playerClean"].value_counts().idxmax() if not wk_rows.empty else None

    all_players = sorted(set(squad_bat.index) | set(squad_bowl.index) | ({keeper} if keeper else set()))
    roster = {}
    for p in all_players:
        has_bat = p in squad_bat.index
        has_bowl = p in squad_bowl.index
        roster[p] = {
            "player": p, "isKeeper": p == keeper,
            "battingScore": round(float(squad_bat.loc[p, "battingScore"]), 2) if has_bat else None,
            "bowlingScore": round(float(squad_bowl.loc[p, "strengthScore"]), 2) if has_bowl else None,
            "battingStats": {
                "innings": int(squad_bat.loc[p, "innings"]), "runs": int(squad_bat.loc[p, "runs"]),
                "avg": float(squad_bat.loc[p, "avg"]), "sr": float(squad_bat.loc[p, "sr"]),
            } if has_bat else None,
            "bowlingStats": {
                "overs": float(squad_bowl.loc[p, "overs"]), "wickets": int(squad_bowl.loc[p, "wickets"]),
                "econ": float(squad_bowl.loc[p, "econ"]), "dotPct": float(squad_bowl.loc[p, "dotPct"]),
            } if has_bowl else None,
        }

    picked = []

    def pick(p):
        if p is not None and p not in picked and p in roster:
            picked.append(p)

    pick(keeper)

    batters_ranked = sorted(
        (p for p in roster if roster[p]["battingScore"] is not None),
        key=lambda p: -roster[p]["battingScore"],
    )
    for p in batters_ranked:
        if len(picked) >= 6:
            break
        pick(p)

    bowlers_ranked = sorted(
        (p for p in roster if roster[p]["bowlingScore"] is not None),
        key=lambda p: -roster[p]["bowlingScore"],
    )

    def bowling_count():
        return sum(1 for p in picked if roster[p]["bowlingScore"] is not None)

    for p in bowlers_ranked:
        if bowling_count() >= 5 or len(picked) >= 11:
            break
        pick(p)

    remaining = sorted(
        (p for p in roster if p not in picked),
        key=lambda p: -((roster[p]["battingScore"] or 0) + (roster[p]["bowlingScore"] or 0)),
    )
    for p in remaining:
        if len(picked) >= 11:
            break
        pick(p)

    players = []
    for p in picked[:11]:
        r = roster[p]
        role = (
            "Wicketkeeper" if r["isKeeper"] else
            "All-rounder" if r["battingScore"] is not None and r["bowlingScore"] is not None else
            "Batter" if r["battingScore"] is not None else
            "Bowler"
        )
        players.append({**r, "role": role})
    return {"players": players, "squadSize": len(roster)}


def load_death_overs(cfg, gladiators, abbrev_map):
    """Last-3-overs bowling figures for OUR team only, from a dedicated over-by-over
    scrape (data/<series>_gladiators_overs.csv — see the rescrape-njsbcl skill's death-overs
    step). Not opponent-specific: this is about who we trust with the ball late, regardless
    of who we're facing. Returns None if that file hasn't been scraped yet."""
    path = DATA_DIR / cfg["overs_csv"]
    if not path.exists():
        return None
    overs = pd.read_csv(path)
    death_parts = []
    for _, g in overs.groupby("matchId"):
        max_over = g["overNum"].max()
        death_parts.append(g[g["overNum"] > max_over - 3])
    death = pd.concat(death_parts, ignore_index=True) if death_parts else overs.iloc[0:0]
    death = death.copy()
    death["bowlerResolved"] = death["bowler"].apply(
        lambda b: abbrev_map.get((gladiators, clean_name(b).lower()), clean_name(b))
    )
    return death


def death_overs_leaders(death_df, min_overs=MIN_DEATH_OVERS, top_n=3):
    """Bowlers ranked by economy across their last-3-overs spells, best first."""
    if death_df is None or death_df.empty:
        return []
    rows = []
    for player, g in death_df.groupby("bowlerResolved"):
        overs_bowled = len(g)
        if overs_bowled < min_overs:
            continue
        runs = int(g["runs"].sum())
        rows.append({
            "player": player, "oversBowled": overs_bowled, "runs": runs,
            "econ": round(runs / overs_bowled, 2),
        })
    return sorted(rows, key=lambda r: r["econ"])[:top_n]


def dismissal_breakdown(bat, team, player):
    sub = bat[(bat["team"] == team) & (bat["playerClean"] == player) & bat["dtype"].notna()]
    total = len(sub)
    if total == 0:
        return {"total": 0, "breakdown": []}
    counts = sub["dtype"].value_counts()
    breakdown = [{"type": t, "count": int(c), "pct": round(100 * c / total, 1)} for t, c in counts.items()]
    return {"total": total, "breakdown": breakdown}


def wickettype_breakdown(bat, bowler_full_name):
    sub = bat[(bat["bowlerResolved"] == bowler_full_name) & bat["dtype"].notna()]
    total = len(sub)
    if total == 0:
        return {"total": 0, "breakdown": []}
    counts = sub["dtype"].value_counts()
    breakdown = [{"type": t, "count": int(c), "pct": round(100 * c / total, 1)} for t, c in counts.items()]
    return {"total": total, "breakdown": breakdown}


def toss_advice(results, team):
    sub = results[(results["team"] == team) & (results["result"] != "Tie")]
    bat1 = sub[sub["battedFirst"]]
    bat2 = sub[~sub["battedFirst"]]
    bat1_wins = int((bat1["result"] == "Win").sum())
    bat2_wins = int((bat2["result"] == "Win").sum())
    bat1_n, bat2_n = len(bat1), len(bat2)
    bat1_pct = round(100 * bat1_wins / bat1_n, 0) if bat1_n else None
    bat2_pct = round(100 * bat2_wins / bat2_n, 0) if bat2_n else None
    avg_score_bat1 = round(bat1["teamScore"].mean(), 0) if bat1_n else None
    avg_chase_success = round(bat2[bat2["result"] == "Win"]["teamScore"].mean(), 0) if (bat2["result"] == "Win").any() else None

    recommendation, reason = None, None
    if bat1_pct is not None and bat2_pct is not None and bat1_n >= 3 and bat2_n >= 3:
        if bat2_pct < bat1_pct - 10:
            recommendation = "bat"
            reason = f"They win only {bat2_pct:.0f}% chasing vs {bat1_pct:.0f}% setting a total — bat first and force them to chase."
        elif bat1_pct < bat2_pct - 10:
            recommendation = "bowl"
            reason = f"They win only {bat1_pct:.0f}% batting first vs {bat2_pct:.0f}% chasing — bowl first and put them in."
        else:
            recommendation = "even"
            reason = f"No strong lean ({bat1_pct:.0f}% batting first vs {bat2_pct:.0f}% chasing) — pick based on conditions."
    else:
        recommendation = "insufficient"
        reason = "Not enough completed matches yet for a confident toss recommendation."

    return {
        "battingFirst": {"matches": bat1_n, "wins": bat1_wins, "winPct": bat1_pct, "avgScore": avg_score_bat1},
        "chasing": {"matches": bat2_n, "wins": bat2_wins, "winPct": bat2_pct, "avgChaseSuccess": avg_chase_success},
        "recommendation": recommendation, "reason": reason,
    }


def par_score_and_target(results, team, min_sample=3):
    """Two matchup-specific numbers for facing `team`:
    - parScoreToSet: the average total that has beaten them this season (across all their
      losses, whether they batted first or second) — what to aim for if we bat first.
    - targetToChase: their average score when batting first (win or lose) — a read on what
      we'll likely need to chase if we bowl first.
    Both require a minimum sample of qualifying matches or return None (not enough data)."""
    losses = results[(results["team"] == team) & (results["result"] == "Loss")]
    par_score = round(losses["oppScore"].mean()) if len(losses) >= min_sample else None

    bat1 = results[(results["team"] == team) & (results["battedFirst"])]
    target = round(bat1["teamScore"].mean()) if len(bat1) >= min_sample else None

    return {
        "parScoreToSet": {"value": par_score, "sampleSize": int(len(losses))},
        "targetToChase": {"value": target, "sampleSize": int(len(bat1))},
    }


def boundary_dependency(bat, team):
    sub = bat[bat["team"] == team]
    runs = sub["R"].sum()
    boundary_runs = sub["4s"].sum() * 4 + sub["6s"].sum() * 6
    return round(100 * boundary_runs / runs, 1) if runs > 0 else 0


def head_to_head(results, gladiators, opponent):
    sub = results[(results["team"] == gladiators) & (results["opponent"] == opponent)]
    matches = []
    for _, r in sub.iterrows():
        matches.append({
            "matchId": int(r["matchId"]), "battedFirst": bool(r["battedFirst"]),
            "gladiatorsScore": int(r["teamScore"]), "opponentScore": int(r["oppScore"]),
            "result": r["result"],
        })
    wins = int((sub["result"] == "Win").sum())
    losses = int((sub["result"] == "Loss").sum())
    ties = int((sub["result"] == "Tie").sum())
    return {"played": len(sub), "wins": wins, "losses": losses, "ties": ties, "matches": matches}


def load_points_table(cfg):
    """team -> {group, rank, rankOf, mat, won, lost, tie, pts, winPct, netRR}."""
    pts = pd.read_csv(DATA_DIR / cfg["points_csv"])
    group_sizes = pts.groupby("group").size().to_dict()
    out = {}
    for _, r in pts.iterrows():
        # a handful of rows have a trailing "*" (site footnote for a points adjustment,
        # e.g. forfeit penalty) — strip it, the numeric value itself is still correct
        pts_match = re.match(r"-?\d+", str(r["pts"]))
        out[r["team"].strip()] = {
            "group": r["group"], "rank": int(r["rank"]), "rankOf": int(group_sizes[r["group"]]),
            "mat": int(r["mat"]), "won": int(r["won"]), "lost": int(r["lost"]), "tie": int(r["tie"]),
            "pts": int(pts_match.group()) if pts_match else None,
            "winPct": float(str(r["winpct"]).rstrip("%")),
            "netRR": float(r["netrr"]),
        }
    return out


def compute_elo(results, track_team=None):
    """Standard Elo, processed in matchId order (a solid chronological proxy — matchIds
    increase monotonically with match date on this site). Returns team -> rating, plus
    (if track_team is given) that team's rating after each of its own matches, for
    charting its form trajectory across the season."""
    rating = {}
    history = []
    one_row_per_match = results.drop_duplicates("matchId", keep="first").sort_values("matchId")
    for _, r in one_row_per_match.iterrows():
        a, b = r["team"], r["opponent"]
        ra = rating.setdefault(a, ELO_START)
        rb = rating.setdefault(b, ELO_START)
        exp_a = 1 / (1 + 10 ** ((rb - ra) / 400))
        if r["result"] == "Win":
            actual_a = 1.0
        elif r["result"] == "Loss":
            actual_a = 0.0
        else:
            actual_a = 0.5
        rating[a] = ra + ELO_K * (actual_a - exp_a)
        rating[b] = rb + ELO_K * ((1 - actual_a) - (1 - exp_a))
        if track_team is not None and track_team in (a, b):
            opponent = b if track_team == a else a
            team_result = r["result"] if track_team == a else (
                "Win" if r["result"] == "Loss" else "Loss" if r["result"] == "Win" else "Tie"
            )
            history.append({
                "matchId": int(r["matchId"]), "elo": round(rating[track_team]),
                "opponent": opponent, "result": team_result,
            })
    return {team: round(r) for team, r in rating.items()}, history


def win_probability(elo_a, elo_b):
    return round(100 / (1 + 10 ** ((elo_b - elo_a) / 400)), 1)


def load_upcoming(cfg, team):
    """All remaining scheduled matches for `team`, soonest first. The dashboard shows
    the first 3 highlighted with the rest behind a "show all" toggle — no cap here so
    that toggle has real data to expand into."""
    df = pd.read_excel(DATA_DIR / cfg["schedule_xlsx"], header=1)
    df = df[(df["Team One"] == team) | (df["Team Two"] == team)].copy()
    df["parsedDate"] = pd.to_datetime(df["Date"], format="%m/%d/%Y", errors="coerce")
    upcoming = df[df["parsedDate"] >= TODAY].sort_values("parsedDate")
    out = []
    for _, r in upcoming.iterrows():
        opponent = r["Team Two"] if r["Team One"] == team else r["Team One"]
        out.append({
            "date": r["parsedDate"].strftime("%a, %b %d %Y"),
            "time": str(r["Time"]),
            "opponent": opponent,
            "venue": r["Ground"] if pd.notna(r["Ground"]) else "TBD",
        })
    return out


def build():
    out = {"generated": TODAY.strftime("%Y-%m-%d"), "series": {}}

    for key, cfg in SERIES.items():
        print(f"=== {key} ===")
        bat, bowl, results, abbrev_map, venue_stats = load_series(key, cfg)
        gladiators = cfg["gladiators"]
        print(f"  venue matching: {venue_stats['matched']}/{venue_stats['totalMatches']} matches "
              f"({venue_stats['noScheduleRow']} no schedule row, {venue_stats['groundMismatch']} ground mismatch)")

        upcoming = load_upcoming(cfg, gladiators)
        print(f"  upcoming: {len(upcoming)}")

        standings = load_points_table(cfg)
        elo, gladiators_elo_history = compute_elo(results, track_team=gladiators)
        gladiators_elo = elo.get(gladiators, ELO_START)
        print(f"  standings loaded: {len(standings)} · elo computed: {len(elo)} · "
              f"{gladiators} elo: {round(gladiators_elo)}")

        # opponents = everyone Samudhra/VRK Gladiators has played or is scheduled to play
        sched = pd.read_excel(DATA_DIR / cfg["schedule_xlsx"], header=1)
        sched_g = sched[(sched["Team One"] == gladiators) | (sched["Team Two"] == gladiators)]
        opponents = sorted({
            (r["Team Two"] if r["Team One"] == gladiators else r["Team One"])
            for _, r in sched_g.iterrows()
        })
        print(f"  opponents: {len(opponents)}")

        weakness_pool = bowler_weakness_pool(bowl)
        strength_pool = bowler_strength_pool(bowl)
        print(f"  bowlers qualifying for weakness ranking (>= {MIN_OVERS_FOR_WEAKNESS} overs): {len(weakness_pool)}")

        death_overs = load_death_overs(cfg, gladiators, abbrev_map)
        death_leaders = death_overs_leaders(death_overs)
        print(f"  death-overs data: {'none scraped yet' if death_overs is None else f'{len(death_overs)} death-over rows, {len(death_leaders)} qualifying bowlers'}")

        teams_data = {}
        all_teams_in_data = sorted(set(bat["team"].unique()) | set([gladiators]))
        for team in all_teams_in_data:
            bat_agg = team_batting_agg(bat, team)
            bowl_agg = team_bowling_agg(bowl, team)
            top_bat = bat_agg.head(3).to_dict("records")
            for b in top_bat:
                b["dismissals"] = dismissal_breakdown(bat, team, b["player"])
                b["recentForm"] = recent_form(bat, team, b["player"])
            top_bowl = bowl_agg.head(3).to_dict("records")
            for b in top_bowl:
                b["wicketTypes"] = wickettype_breakdown(bat, b["player"])

            sub_res = results[results["team"] == team]
            wins = int((sub_res["result"] == "Win").sum())
            losses = int((sub_res["result"] == "Loss").sum())
            ties = int((sub_res["result"] == "Tie").sum())

            team_elo = elo.get(team, ELO_START)
            teams_data[team] = {
                "matches": len(sub_res), "wins": wins, "losses": losses, "ties": ties,
                "topBatsmen": top_bat, "topBowlers": top_bowl,
                "toss": toss_advice(results, team),
                "parTarget": par_score_and_target(results, team),
                "boundaryDependencyPct": boundary_dependency(bat, team),
                "weakBowlers": weak_bowlers(weakness_pool, team),
                "bowlingStrengths": bowling_strengths(strength_pool, team),
                "homeAway": home_away_record(results, team),
                "battingCollapses": detect_collapses(bat, results, team),
                "headToHead": head_to_head(results, gladiators, team) if team != gladiators else None,
                "standing": standings.get(team),
                "elo": team_elo,
                # Gladiators' win probability if they played this team today, per current Elo
                "gladiatorsWinProbability": (
                    None if team == gladiators else win_probability(gladiators_elo, team_elo)
                ),
            }
        print(f"  teams computed: {len(teams_data)}")

        bat_strength_pool = batter_strength_pool(bat)
        best_xi = best_playing_xi(bat, bat_strength_pool, strength_pool, gladiators)
        league_avg_collapse_pct = (
            round(sum(t["battingCollapses"]["collapsePct"] for t in teams_data.values()) / len(teams_data))
            if teams_data else 0
        )
        gladiators_charts = {
            "bestXI": best_xi,
            "eloHistory": gladiators_elo_history,
            "battingLeaderboard": team_batting_agg(bat, gladiators).to_dict("records"),
            "bowlingLeaderboard": team_bowling_agg(bowl, gladiators).to_dict("records"),
            "leagueAvgCollapsePct": league_avg_collapse_pct,
        }
        print(f"  best XI: {len(best_xi['players'])} players from a qualifying squad of {best_xi['squadSize']}")

        out["series"][key] = {
            "label": cfg["label"], "gladiators": gladiators,
            "opponents": opponents, "upcoming": upcoming, "teams": teams_data,
            "deathOversLeaders": death_leaders, "gladiatorsCharts": gladiators_charts,
        }

    js = "// Auto-generated by build_data.py — do not edit by hand.\nconst NJSBCL_DATA = " + json.dumps(out, indent=None) + ";\n"
    OUT_FILE.write_text(js)
    print(f"Wrote {OUT_FILE} ({OUT_FILE.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    build()
