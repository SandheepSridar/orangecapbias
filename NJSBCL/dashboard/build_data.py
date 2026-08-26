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
# Real current date, not a fixed snapshot — load_upcoming() filters the schedule against this,
# so a hardcoded date here would silently stop dropping played matches from "upcoming fixtures"
# once that date passed (caught 2026-08-16: a match played the day before was still showing as
# upcoming because this was frozen at 2026-08-11).
TODAY = datetime.now()

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
    o = float(o)  # accepts both the raw numeric "O" column and balls_to_overs_str()'s "X.Y" strings
    whole = int(o)
    frac = round((o - whole) * 10)
    return whole * 6 + frac


def balls_to_overs_str(b):
    return f"{b // 6}.{b % 6}"


def aggregate_bowling_spells(bowl):
    """A bowler occasionally gets two separate rows in the same match on cricclubs.com
    itself — a genuine second spell, not a scraping artifact (verified 2026-08-22 by
    cross-checking playerId on live scorecards for 3 real cases: Vinit Bharadwaj and
    Sandeep I Shetty in division1 matchId 19930, Vamshidhar Reddy in weekenders matchId
    19523 — all confirmed same person across both their rows). Without this, every
    downstream "this bowler's match figures" lookup (verdict_bowling_strength_*,
    verdict_weak_bowler_*, match_points_table) only ever saw whichever spell happened to
    be the first row, silently dropping the other. Combine into one row per (matchId,
    team, bowlerClean) so those all see the full match figures.

    Known residual risk: the exact same match (weekenders 19417) also has a bowling
    duplicate for "Jithin Varghese" that is NOT a real second spell — it's two different
    Staten Island Strikers players who happen to share a name (confirmed via differing
    playerId on the live scorecard), and this function has no way to tell that apart from
    a genuine spell since the scraper doesn't capture playerId. It gets merged into one
    fake combined figure anyway. Low blast radius today (affects opponent-team
    weak-bowler flagging only, and only if that fabricated line happens to rank among a
    team's 3 weakest), but a real gap — the proper fix is scraping playerId and grouping
    by that instead of by name.

    NOT applied to batting at all: the same name-collision risk applies there too, but
    with no confirmed genuine repeat-innings case to justify merging (unlike bowling,
    where 3 real multi-spell cases were confirmed), the balance favors leaving batting
    rows as scraped and letting dq_checks flag duplicates for a human to eyeball."""
    bowl = bowl.copy()
    bowl["_balls"] = bowl["O"].apply(overs_to_balls)
    agg = bowl.groupby(["matchId", "team", "bowlerClean"], as_index=False).agg(
        bowler=("bowler", "first"), _balls=("_balls", "sum"), M=("M", "sum"),
        Dot=("Dot", "sum"), R=("R", "sum"), W=("W", "sum"),
        wides=("wides", "sum"), noballs=("noballs", "sum"),
    )
    agg["O"] = agg["_balls"].apply(lambda b: float(balls_to_overs_str(b)))
    agg["Econ"] = agg.apply(lambda r: round(r["R"] / (r["_balls"] / 6), 2) if r["_balls"] else 0.0, axis=1)
    return agg.drop(columns="_balls")


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
    bowl = aggregate_bowling_spells(bowl)

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
    """Adds 'venue' ('Home'/'Away') and 'date' columns to `results` by matching each completed
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
        sched_by_pair.setdefault(pair, []).append((ground, r["parsedDate"]))

    one_row_per_match = results.drop_duplicates("matchId", keep="first").sort_values("matchId")
    results_by_pair = {}
    for _, r in one_row_per_match.iterrows():
        pair = frozenset({r["team"].lower(), r["opponent"].lower()})
        results_by_pair.setdefault(pair, []).append((r["matchId"], r["team"], r["opponent"]))

    venue_map = {}  # matchId -> {team: "Home"/"Away"}
    date_map = {}   # matchId -> "Aug 15, 2026" (same regardless of team perspective)
    matched, no_schedule_row, ground_mismatch = 0, 0, 0
    for pair, matches in results_by_pair.items():
        rows = sched_by_pair.get(pair, [])
        for i, (match_id, team, opponent) in enumerate(matches):
            if i >= len(rows):
                no_schedule_row += 1
                continue
            ground, date = rows[i]
            date_map[match_id] = date.strftime("%b %d, %Y")
            ground_norm = ground.lower()
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
    results["date"] = results["matchId"].map(date_map)
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


def key_batsman_win_impact(bat, results, team, player, min_each_bucket=3):
    """How much `team`'s win rate swings with `player`'s batting: split his innings into
    at-or-above vs below his own season median score, and compare the team's win% in each
    bucket. Answers "how much does it help to get him out early?" — low-score innings are
    the closest proxy available for an early dismissal (no per-match dismissal-over data
    exists for opponent teams, only runs scored, same limitation as elsewhere in this file).
    Requires at least `min_each_bucket` matches on both sides of the split, else returns None
    (too small a sample in a ~14-match season to mean anything)."""
    sub = bat[(bat["team"] == team) & (bat["playerClean"] == player)][["matchId", "R"]].copy()
    res_map = results[(results["team"] == team) & (results["result"] != "Tie")].set_index("matchId")["result"]
    sub = sub[sub["matchId"].isin(res_map.index)]
    if len(sub) < min_each_bucket * 2:
        return None
    median = sub["R"].median()
    sub["result"] = sub["matchId"].map(res_map)
    high = sub[sub["R"] >= median]
    low = sub[sub["R"] < median]
    if len(high) < min_each_bucket or len(low) < min_each_bucket:
        return None
    high_win = round(100 * (high["result"] == "Win").mean())
    low_win = round(100 * (low["result"] == "Win").mean())
    if high_win <= low_win:
        # Inverted or flat split: scoring more didn't actually track with winning more, so
        # this player isn't a "key batsman" signal by this metric — just noise on a small
        # sample. Reporting it anyway would let the right/wrong verdicts fire backwards.
        return None
    return {
        "threshold": int(median), "highN": len(high), "lowN": len(low),
        "highWinPct": high_win, "lowWinPct": low_win, "swing": high_win - low_win,
    }


def win_dependency(bat, bowl, results, team, min_matches=6, min_each_bucket=3,
                    min_bat_median=10, min_avg_overs=2.0, top_n=6):
    """Ranks every player who's batted OR bowled for `team` by how much the team's win rate
    swings between their good and bad games — a role-agnostic "who do we depend on to win"
    leaderboard, not just a batting-runs one. For batters: at-or-above vs below their own
    season median runs that innings. For bowlers: at-or-below (better) vs above (worse) their
    own season median economy that spell. Both sides need `min_each_bucket` matches, and a
    player needs `min_matches` total appearances to be considered at all — this is a small
    (~14-match) season, so this stays a "notable pattern," not a rigorous causal claim; framed
    that way in the UI copy, not as this file's problem to solve.

    Two extra floors keep this from surfacing noise: `min_bat_median` drops tail-order
    batters whose "good" bucket is really just "got to bat at all" (a median of 3-4 runs
    splits mostly on whether he faced more than a couple of balls, not on a real knock), and
    `min_avg_overs` drops one-over part-timers whose economy swings wildly on a small sample."""
    res_map = results[(results["team"] == team) & (results["result"] != "Tie")].set_index("matchId")["result"]

    out = []
    bat_sub = bat[bat["team"] == team]
    for player, g in bat_sub.groupby("playerClean"):
        g = g[g["matchId"].isin(res_map.index)]
        if len(g) < min_matches:
            continue
        median = g["R"].median()
        if median < min_bat_median:
            continue
        result = g["matchId"].map(res_map)
        high = result[g["R"] >= median]
        low = result[g["R"] < median]
        if len(high) < min_each_bucket or len(low) < min_each_bucket:
            continue
        good_win = 100 * (high == "Win").mean()
        bad_win = 100 * (low == "Win").mean()
        out.append({
            "player": player, "role": "bat", "matches": int(len(g)),
            "metric": f"runs (median {int(median)})",
            "goodWinPct": round(good_win), "badWinPct": round(bad_win),
            "swing": round(good_win - bad_win),
        })

    bowl_sub = bowl[bowl["team"] == team]
    for player, g in bowl_sub.groupby("bowlerClean"):
        g = g[g["matchId"].isin(res_map.index)]
        if len(g) < min_matches:
            continue
        avg_overs = g["O"].apply(overs_to_balls).mean() / 6
        if avg_overs < min_avg_overs:
            continue
        median = g["Econ"].median()
        result = g["matchId"].map(res_map)
        good = result[g["Econ"] <= median]   # lower economy = better bowling
        bad = result[g["Econ"] > median]
        if len(good) < min_each_bucket or len(bad) < min_each_bucket:
            continue
        good_win = 100 * (good == "Win").mean()
        bad_win = 100 * (bad == "Win").mean()
        out.append({
            "player": player, "role": "bowl", "matches": int(len(g)),
            "metric": f"economy (median {median:.1f})",
            "goodWinPct": round(good_win), "badWinPct": round(bad_win),
            "swing": round(good_win - bad_win),
        })

    out = [r for r in out if r["swing"] > 0]  # a 0/negative swing isn't "who we depend on"
    out.sort(key=lambda r: r["swing"], reverse=True)
    return out[:top_n]


def team_recent_form(results, team, n=5):
    """Last-n match results for `team` (any opponent, not just Gladiators), oldest to
    newest — matchId order as the chronological proxy used everywhere else in this file.
    Powers the W/L/T form strip shown next to upcoming fixtures."""
    sub = results[results["team"] == team].sort_values("matchId")
    if sub.empty:
        return []
    last_n = sub.tail(n)
    return [
        {"matchId": int(r["matchId"]), "opponent": r["opponent"], "result": r["result"]}
        for _, r in last_n.iterrows()
    ]


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
        dots = int(g["Dot"].sum())
        econ = round(runs / (balls / 6), 2) if balls > 0 else 0
        avg = round(runs / wkts, 1) if wkts > 0 else None
        dot_pct = round(100 * dots / balls, 1) if balls > 0 else 0.0
        rows.append({
            "player": player, "wickets": wkts, "overs": balls_to_overs_str(balls),
            "runs": runs, "econ": econ, "avg": avg, "dotPct": dot_pct,
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


def build_squad_roster(bat, bowl, bat_pool, bowl_pool, team):
    """Every player who has appeared for `team` this season — batted or bowled at least
    once — not just those clearing batter_strength_pool/bowler_strength_pool's qualifying
    thresholds. A fringe player who's only played a couple of games still needs to show
    up as an emergency fallback option when regulars are marked unavailable, rather than
    disappearing from the list entirely.

    battingScore/bowlingScore (the z-scored value select_xi() ranks candidates by) are
    still only set for players who clear those thresholds — a 1-innings sample isn't a
    reliable signal to actively rank someone highly on. Unscored players are still real
    roster entries though: select_xi()'s "fill remaining spots" step treats a missing
    score as neutral (0), so they're only ever picked once every qualifying option is
    already in the XI or unavailable — exactly the "last resort" role they should play."""
    team_bat_all = team_batting_agg(bat, team).set_index("player")
    team_bowl_all = team_bowling_agg(bowl, team).set_index("player")
    squad_bat = bat_pool[bat_pool["team"] == team].set_index("player") if not bat_pool.empty else bat_pool
    squad_bowl = bowl_pool[bowl_pool["team"] == team].set_index("player") if not bowl_pool.empty else bowl_pool

    wk_rows = bat[(bat["team"] == team) & (bat["player"].str.contains("†", na=False))]
    keeper = wk_rows["playerClean"].value_counts().idxmax() if not wk_rows.empty else None

    all_players = sorted(set(team_bat_all.index) | set(team_bowl_all.index) | ({keeper} if keeper else set()))
    roster = {}
    for p in all_players:
        has_bat = p in team_bat_all.index
        has_bowl = p in team_bowl_all.index
        roster[p] = {
            "player": p, "isKeeper": p == keeper,
            "battingScore": round(float(squad_bat.loc[p, "battingScore"]), 2) if p in squad_bat.index else None,
            "bowlingScore": round(float(squad_bowl.loc[p, "strengthScore"]), 2) if p in squad_bowl.index else None,
            "battingStats": {
                "innings": int(team_bat_all.loc[p, "innings"]), "runs": int(team_bat_all.loc[p, "runs"]),
                "avg": float(team_bat_all.loc[p, "avg"]), "sr": float(team_bat_all.loc[p, "sr"]),
            } if has_bat else None,
            "bowlingStats": {
                "wickets": int(team_bowl_all.loc[p, "wickets"]), "econ": float(team_bowl_all.loc[p, "econ"]),
                "dotPct": float(team_bowl_all.loc[p, "dotPct"]),
            } if has_bowl else None,
        }
    return roster


def select_xi(roster):
    """Pure selection logic, given a roster dict (player -> stats/scores) already
    filtered to available players: the keeper, the best 5 remaining batting options by
    battingScore, enough bowling options by bowlingScore to cover a full attack (aiming
    for 5 recognized bowlers in the XI), then fills any remaining spots with the best
    leftover combined value. Deliberately side-effect-free and dependency-free (no
    pandas) so this same logic can be ported 1:1 to JS for live client-side reshuffling
    when the user marks players unavailable — see charts.js's selectXI()."""
    picked = []

    def pick(p):
        if p is not None and p not in picked and p in roster:
            picked.append(p)

    keeper = next((p for p, r in roster.items() if r["isKeeper"]), None)
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

    def combined_value(p):
        scores = [s for s in (roster[p]["battingScore"], roster[p]["bowlingScore"]) if s is not None]
        # a player with zero qualifying scores (never proven at either discipline this
        # season) must rank below one with even a single real, below-average score —
        # otherwise an unproven name looks "neutral" (0) and outranks a known, if
        # mediocre, regular. Only pick the unproven as a genuine last resort.
        return sum(scores) if scores else float("-inf")

    remaining = sorted((p for p in roster if p not in picked), key=lambda p: -combined_value(p))
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
    return players


def best_playing_xi(bat, bowl, bat_pool, bowl_pool, team):
    """Default Playing XI (everyone available) plus the full candidate roster, so the
    frontend can re-run select_xi() itself against a subset when players are marked
    unavailable."""
    roster = build_squad_roster(bat, bowl, bat_pool, bowl_pool, team)
    return {
        "players": select_xi(roster),
        "roster": list(roster.values()),
        "squadSize": len(roster),
    }


def load_gladiators_overs(cfg, gladiators, abbrev_map):
    """Full-season over-by-over bowling detail for OUR team only (one row per over bowled),
    from a dedicated over-by-over scrape (data/<series>_gladiators_overs.csv — see the
    rescrape-njsbcl skill's over-by-over step). Not opponent-specific: this is about our own
    bowling patterns regardless of who we're facing. Returns None if that file hasn't been
    scraped yet."""
    path = DATA_DIR / cfg["overs_csv"]
    if not path.exists():
        return None
    overs = pd.read_csv(path).copy()
    overs["bowlerResolved"] = overs["bowler"].apply(
        lambda b: abbrev_map.get((gladiators, clean_name(b).lower()), clean_name(b))
    )
    return overs


def death_overs_only(overs_df):
    """Last-3-overs-of-the-innings subset of a full-season overs dataframe."""
    if overs_df is None or overs_df.empty:
        return overs_df
    death_parts = []
    for _, g in overs_df.groupby("matchId"):
        max_over = g["overNum"].max()
        death_parts.append(g[g["overNum"] > max_over - 3])
    return pd.concat(death_parts, ignore_index=True) if death_parts else overs_df.iloc[0:0]


PHASE_BOUNDARIES = [(1, 4), (5, 8), (9, 12), (13, 16)]
PHASE_LABELS = ["Overs 1-4", "Overs 5-8", "Overs 9-12", "Overs 13-16"]
MIN_PHASE_OVERS = 3


def bowler_phase_breakdown(overs_df, min_overs=MIN_PHASE_OVERS):
    """Which of our bowlers is strongest in each 4-over block of a 16-over innings, ranked by
    a composite of dot-ball %, wicket rate (wickets/over), and extras rate (wides+noballs/over,
    negated) — each z-scored against the other bowlers who qualify in that same block, mirroring
    the whole-season bowlingStrengths z-scoring pattern. Needs the ball-by-ball detail columns
    from the extended over-by-over scrape (legalBalls/dots/wickets/wides/noballs) — returns []
    on the older runs-only scrape format."""
    if overs_df is None or overs_df.empty or "legalBalls" not in overs_df.columns:
        return []
    phases = []
    for label, (lo, hi) in zip(PHASE_LABELS, PHASE_BOUNDARIES):
        block = overs_df[(overs_df["overNum"] >= lo) & (overs_df["overNum"] <= hi)]
        bowlers = []
        for player, g in block.groupby("bowlerResolved"):
            legal_balls = int(g["legalBalls"].sum())
            overs_bowled = legal_balls / 6
            if overs_bowled < min_overs:
                continue
            dots = int(g["dots"].sum())
            wickets = int(g["wickets"].sum())
            extras = int(g["wides"].sum() + g["noballs"].sum())
            runs = int(g["runs"].sum())
            bowlers.append({
                "player": player, "overs": round(overs_bowled, 1), "runs": runs, "wickets": wickets,
                "econ": round(runs / overs_bowled, 2),
                "dotPct": round(100 * dots / legal_balls, 1),
                "wicketRate": round(wickets / overs_bowled, 2),
                "extrasRate": round(extras / overs_bowled, 2),
            })
        if bowlers:
            def zscore(vals, x):
                mean = sum(vals) / len(vals)
                std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
                return (x - mean) / std if std > 0 else 0.0
            dot_vals = [b["dotPct"] for b in bowlers]
            wkt_vals = [b["wicketRate"] for b in bowlers]
            ext_vals = [b["extrasRate"] for b in bowlers]
            for b in bowlers:
                b["phaseScore"] = round((
                    zscore(dot_vals, b["dotPct"]) + zscore(wkt_vals, b["wicketRate"])
                    - zscore(ext_vals, b["extrasRate"])
                ) / 3, 2)
            bowlers.sort(key=lambda b: -b["phaseScore"])
        phases.append({"phase": label, "bowlers": bowlers})
    return phases


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


def batting_position_avg(bat, team):
    """Average batting position per player this season, derived from scorecard row order
    within each (matchId, team) innings — same "row order = batting order" assumption
    detect_collapses() already relies on."""
    sub = bat[bat["team"] == team].copy()
    sub["position"] = sub.groupby("matchId").cumcount() + 1
    return sub.groupby("playerClean")["position"].mean().round(1).to_dict()


def insight_phase_bowling(bowler_phases):
    """AI-insight candidate: the phase with the biggest gap between its top-ranked bowler
    (by phaseScore) and whoever actually bowled the most overs there, when they differ —
    a direct 'this bowler should get more of the ball in this block' signal straight from
    the bowler-by-phase breakdown."""
    best = None
    for phase in bowler_phases:
        bowlers = phase["bowlers"]
        if len(bowlers) < 2:
            continue
        top = bowlers[0]
        most_used = max(bowlers, key=lambda b: b["overs"])
        if most_used["player"] == top["player"]:
            continue
        gap = top["phaseScore"] - most_used["phaseScore"]
        if gap <= 0:
            continue
        if best is None or gap > best["gap"]:
            best = {"phase": phase["phase"], "top": top, "mostUsed": most_used, "gap": gap}
    if best is None:
        return None
    top, most_used, phase_label = best["top"], best["mostUsed"], best["phase"]
    phase_bounds = PHASE_BOUNDARIES[PHASE_LABELS.index(phase_label)]
    return {
        "title": f"Bowl {top['player'].split()[0]} more in the {phase_label.lower()}",
        "detail": (
            f"In {phase_label.lower()} this season, {top['player']} has the strongest record of "
            f"anyone who's bowled there — econ {top['econ']}, {top['dotPct']}% dot balls, "
            f"{top['wicketRate']} wkt/over across {top['overs']} overs. But {most_used['player']} "
            f"has actually bowled the most there ({most_used['overs']} overs, econ "
            f"{most_used['econ']}) despite a clearly worse record in that block."
        ),
        "type": "phaseBowling", "player": top["player"],
        "phaseLabel": phase_label, "phaseBounds": phase_bounds,
    }


def insight_batting_order(roster, avg_position):
    """AI-insight candidate: the qualifying batter with the biggest gap between their
    batting-quality rank (battingScore, best first) and their actual average batting
    position this season — the strongest 'should be batting higher' signal available."""
    candidates = [
        (r["player"], r["battingScore"], avg_position[r["player"]])
        for r in roster if r["battingScore"] is not None and r["player"] in avg_position
    ]
    if len(candidates) < 2:
        return None
    candidates.sort(key=lambda c: -c[1])
    player, score, pos, rank, gap = max(
        ((player, score, pos, rank, pos - rank) for rank, (player, score, pos) in enumerate(candidates, start=1)),
        key=lambda c: c[4],
    )
    if gap <= 0:
        return None
    return {
        "title": f"Move {player.split()[0]} up the batting order",
        "detail": (
            f"{player} has the #{rank} batting quality score in the squad this season "
            f"(average + strike rate, z-scored against the whole league) but has batted at an "
            f"average position of {pos:.1f} — well down the order for someone rated that highly."
        ),
        "type": "battingOrder", "player": player, "seasonAvgPosition": pos,
    }


def insight_bowling_workload(bowling_strengths, bowling_leaderboard):
    """AI-insight candidate: season-wide version of the same underused-talent idea — our
    best economy/dot-rate bowler (bowlingStrengths) vs whoever's actually bowled the most
    overs overall, when they differ."""
    if not bowling_strengths or not bowling_leaderboard:
        return None
    top = bowling_strengths[0]
    most_used = max(bowling_leaderboard, key=lambda p: overs_to_balls(p["overs"]))
    if most_used["player"] == top["player"]:
        return None
    if overs_to_balls(most_used["overs"]) <= overs_to_balls(top["overs"]):
        return None
    return {
        "title": f"Bowl {top['player'].split()[0]} more overall",
        "detail": (
            f"{top['player']} rates as our best bowler this season on economy + dot-ball rate "
            f"(econ {top['econ']}, {top['dotPct']}% dots) but has bowled {top['overs']} overs "
            f"total, while {most_used['player']} has bowled the most of anyone on the squad "
            f"({most_used['overs']} overs, econ {most_used['econ']})."
        ),
        "type": "bowlingWorkload", "player": top["player"],
    }


def build_ai_insights(bowler_phases, roster, avg_position, bowling_strengths, bowling_leaderboard):
    """Top-3 (or fewer, if a series doesn't have enough data for one) data-backed 'things the
    team should try that it isn't doing now' — each generator surfaces one concrete gap between
    who the numbers say is best and who's actually getting the overs/batting position."""
    generators = [
        lambda: insight_phase_bowling(bowler_phases),
        lambda: insight_batting_order(roster, avg_position),
        lambda: insight_bowling_workload(bowling_strengths, bowling_leaderboard),
    ]
    return [r for r in (g() for g in generators) if r is not None]


def latest_completed_match(results, team):
    """Most recent completed match for `team` (matchId order as the chronological proxy used
    everywhere else in this file)."""
    sub = results[results["team"] == team].sort_values("matchId")
    if sub.empty:
        return None
    r = sub.iloc[-1]
    return {
        "matchId": int(r["matchId"]), "opponent": r["opponent"], "result": r["result"],
        "teamScore": int(r["teamScore"]), "oppScore": int(r["oppScore"]),
        "battedFirst": bool(r["battedFirst"]), "date": r["date"] if pd.notna(r["date"]) else None,
    }


# ── Match points table (Star of the Match) ──────────────────────────────
# A transparent, fixed-formula points system (batting + bowling only — no fielding credit,
# since fielder names aren't extracted from dismissal text anywhere in this pipeline) so
# "who had the biggest impact" is a disclosed calculation, not a judgment call. Modeled on the
# common fantasy-cricket points pattern: base value for the raw output (runs / wickets + dots),
# plus a strike-rate/economy modifier once a player has faced/bowled enough to make the rate
# meaningful.
BATTING_POINTS_MIN_BALLS = 10
BOWLING_POINTS_MIN_OVERS = 2.0


def batting_points(runs, balls, fours, sixes):
    pts = runs + fours * 1 + sixes * 2
    if balls >= BATTING_POINTS_MIN_BALLS:
        sr = 100 * runs / balls if balls else 0
        if sr >= 150:
            pts += 10
        elif sr >= 125:
            pts += 5
        elif sr < 60:
            pts -= 5
    return round(pts, 1)


def bowling_points(wickets, runs_conceded, dots, balls):
    overs = balls / 6
    pts = wickets * 20 + dots * 1
    if overs >= BOWLING_POINTS_MIN_OVERS:
        econ = runs_conceded / overs if overs else 0
        if econ <= 4:
            pts += 10
        elif econ <= 6:
            pts += 5
        elif econ >= 10:
            pts -= 10
        elif econ >= 8:
            pts -= 5
    return round(pts, 1)


def league_points_stats(bat, bowl):
    """Mean/std of batting_points()/bowling_points() across every row in the whole league this
    season — the baseline match_points_table() z-scores against. Needed because the two raw
    scales aren't comparable: a routine bowling spell (a few wickets, a run of dots) racks up
    far more raw points than a routine batting innings just because wickets are worth 20 points
    apiece and dots add up fast, so ranking on raw points alone structurally favours bowling
    (and, by stacking both, all-rounders) over specialist batting. Z-scoring each discipline
    against its own league-wide distribution before combining removes that scale bias — a
    performance is judged by how it compares to a normal day in the *same* discipline, not
    against the other one's bigger numbers. Verified 2026-08-16: median bowling spell this
    season scores ~32-35 raw points vs ~3-5 for a median batting innings, a ~7-10x gap that
    made a modest 3-wicket haul routinely outscore a well-struck fifty before this fix."""
    bat_pts = bat.apply(lambda r: batting_points(r["R"], r["B"], r["4s"], r["6s"]), axis=1)
    bowl_balls = bowl["O"].apply(overs_to_balls)
    bowl_pts = bowl.apply(
        lambda r: bowling_points(r["W"], r["R"], r["Dot"], overs_to_balls(r["O"])), axis=1
    )
    return {
        "battingMean": bat_pts.mean(), "battingStd": bat_pts.std(),
        "bowlingMean": bowl_pts.mean(), "bowlingStd": bowl_pts.std(),
    }


def match_points_table(bat, bowl, match_id, team, league_stats):
    """Every one of `team`'s players who batted or bowled in `match_id`, ranked by a combined
    impact score (sum of whichever z-scores apply — batting only, bowling only, or both for an
    all-rounder) — the full, disclosed working behind the Star of the Match pick (rows[0])."""
    bat_sub = bat[(bat["matchId"] == match_id) & (bat["team"] == team)]
    bowl_sub = bowl[(bowl["matchId"] == match_id) & (bowl["team"] == team)]
    points = {}
    for _, r in bat_sub.iterrows():
        p = r["playerClean"]
        points.setdefault(p, {"player": p, "battingPoints": 0.0, "bowlingPoints": 0.0,
                               "battingZ": None, "bowlingZ": None,
                               "battingLine": None, "bowlingLine": None})
        bp = batting_points(r["R"], r["B"], r["4s"], r["6s"])
        points[p]["battingPoints"] = bp
        points[p]["battingZ"] = round((bp - league_stats["battingMean"]) / league_stats["battingStd"], 2) \
            if league_stats["battingStd"] else 0.0
        points[p]["battingLine"] = f"{int(r['R'])} ({int(r['B'])}b)"
    for _, r in bowl_sub.iterrows():
        p = r["bowlerClean"]
        balls = overs_to_balls(r["O"])
        points.setdefault(p, {"player": p, "battingPoints": 0.0, "bowlingPoints": 0.0,
                               "battingZ": None, "bowlingZ": None,
                               "battingLine": None, "bowlingLine": None})
        bp = bowling_points(int(r["W"]), int(r["R"]), int(r["Dot"]), balls)
        points[p]["bowlingPoints"] = bp
        points[p]["bowlingZ"] = round((bp - league_stats["bowlingMean"]) / league_stats["bowlingStd"], 2) \
            if league_stats["bowlingStd"] else 0.0
        points[p]["bowlingLine"] = f"{int(r['W'])}/{int(r['R'])} ({balls_to_overs_str(balls)} ov)"
    rows = list(points.values())
    for r in rows:
        zs = [z for z in (r["battingZ"], r["bowlingZ"]) if z is not None]
        r["impactScore"] = round(sum(zs), 2) if zs else 0.0
    rows.sort(key=lambda r: -r["impactScore"])
    return rows


# ── Post-match "what we got right / wrong" verdicts ─────────────────────
# Each generator checks one pre-match signal the dashboard already surfaces (toss read, par
# score, key-batsman threshold, bowling strengths/weaknesses) against what actually happened in
# the latest completed match, and returns a verdict only when the evidence is reasonably
# clear-cut — never forced to fill a quota. Deliberately excludes squad-selection/availability
# ("did our top picks even play") from right/wrong — who's on the field is volatile and not
# something this recap should second-guess; every check here is about how the players who
# actually took the field performed, not who they were.
PAR_TARGET_NEAR = 5     # runs within par counts as "met it"
PAR_TARGET_MISS = 15    # runs short of par counts as a clear miss
ECON_MARGIN = 1.0       # how far off season economy counts as "held up" / "let him off"


def verdict_toss_right(match, them_toss):
    rec = them_toss["recommendation"]
    if rec not in ("bat", "bowl"):
        return None
    followed = (rec == "bat" and match["battedFirst"]) or (rec == "bowl" and not match["battedFirst"])
    if followed and match["result"] == "Win":
        choice = "batted first" if match["battedFirst"] else "bowled first"
        return {"title": f"Read the format right — we {choice}, as advised",
                "detail": them_toss["reason"] + f" We {choice} today and won."}
    return None


def verdict_toss_wrong(match, them_toss):
    rec = them_toss["recommendation"]
    if rec not in ("bat", "bowl"):
        return None
    followed = (rec == "bat" and match["battedFirst"]) or (rec == "bowl" and not match["battedFirst"])
    if followed and match["result"] == "Loss":
        choice = "batted first" if match["battedFirst"] else "bowled first"
        return {"title": "Followed the format read and still lost",
                "detail": them_toss["reason"] + f" We {choice} today, matching the read, but lost anyway."}
    return None


def verdict_par_target_right(match, them_par):
    if match["battedFirst"]:
        par = them_par["parScoreToSet"]["value"]
        if par is None or match["teamScore"] < par - PAR_TARGET_NEAR:
            return None
        return {"title": f"Posted at/near the par score ({match['teamScore']} vs par {par})",
                "detail": f"Par score to set against {match['opponent']} is {par} runs (their "
                          f"average losing total this season). We scored {match['teamScore']}."}
    target = them_par["targetToChase"]["value"]
    if target is None or match["oppScore"] > target - PAR_TARGET_NEAR:
        return None
    return {"title": "Held them well below their usual first-innings total",
            "detail": f"{match['opponent']} average {target} runs batting first this season; "
                      f"we held them to {match['oppScore']}."}


def verdict_par_target_wrong(match, them_par):
    if match["battedFirst"]:
        par = them_par["parScoreToSet"]["value"]
        if par is None or match["teamScore"] > par - PAR_TARGET_MISS:
            return None
        return {"title": "Fell short of the par score",
                "detail": f"Par score to set against {match['opponent']} is {par} (their average "
                          f"losing total). We managed {match['teamScore']}."}
    target = them_par["targetToChase"]["value"]
    if target is None or match["oppScore"] < target + PAR_TARGET_MISS:
        return None
    return {"title": "Let them well past their usual first-innings total",
            "detail": f"{match['opponent']} average {target} runs batting first this season; "
                      f"they posted {match['oppScore']} against us."}


def verdict_key_batsman_right(match, bat, them):
    impact = them.get("keyBatsmanWinImpact")
    top = them["topBatsmen"][0]["player"] if them["topBatsmen"] else None
    if not impact or not top:
        return None
    sub = bat[(bat["matchId"] == match["matchId"]) & (bat["team"] == match["opponent"]) & (bat["playerClean"] == top)]
    if sub.empty:
        return None
    runs = int(sub.iloc[0]["R"])
    if runs >= impact["threshold"]:
        return None
    return {"title": f"Held {top} below his tipping point",
            "detail": f"{match['opponent']} win {impact['highWinPct']}% of matches when {top} scores "
                      f"{impact['threshold']}+, but just {impact['lowWinPct']}% when he doesn't. "
                      f"He made {runs} today."}


def verdict_key_batsman_wrong(match, bat, them):
    impact = them.get("keyBatsmanWinImpact")
    top = them["topBatsmen"][0]["player"] if them["topBatsmen"] else None
    if not impact or not top:
        return None
    sub = bat[(bat["matchId"] == match["matchId"]) & (bat["team"] == match["opponent"]) & (bat["playerClean"] == top)]
    if sub.empty:
        return None
    runs = int(sub.iloc[0]["R"])
    if runs < impact["threshold"]:
        return None
    return {"title": f"Let {top} bat past his tipping point",
            "detail": f"{match['opponent']} win {impact['highWinPct']}% of matches when {top} scores "
                      f"{impact['threshold']}+ (vs {impact['lowWinPct']}% when he doesn't) — he made "
                      f"{runs} today."}


def verdict_bowling_strength_right(match, bowl, gladiators, us_strengths):
    for b in us_strengths:
        sub = bowl[(bowl["matchId"] == match["matchId"]) & (bowl["team"] == gladiators) & (bowl["bowlerClean"] == b["player"])]
        if sub.empty:
            continue
        r = sub.iloc[0]
        balls = overs_to_balls(r["O"])
        if balls == 0:
            continue
        econ_today = r["R"] / (balls / 6)
        if econ_today <= b["econ"] + ECON_MARGIN:
            return {"title": f"{b['player']} backed up his season economy",
                    "detail": f"Rated our most economical bowler this season (econ {b['econ']}). "
                              f"Today: {int(r['W'])}/{int(r['R'])} at econ {round(econ_today, 2)}."}
    return None


def verdict_bowling_strength_wrong(match, bowl, gladiators, us_strengths):
    """Only fires for a bowler who actually took the ball today — who did or didn't feature is
    squad selection, not a strategic call this recap should second-guess. This checks how the
    bowlers we had performed, not who was picked."""
    for b in us_strengths:
        sub = bowl[(bowl["matchId"] == match["matchId"]) & (bowl["team"] == gladiators) & (bowl["bowlerClean"] == b["player"])]
        if sub.empty:
            continue
        r = sub.iloc[0]
        balls = overs_to_balls(r["O"])
        if balls == 0:
            continue
        econ_today = r["R"] / (balls / 6)
        if econ_today > b["econ"] + ECON_MARGIN:
            return {"title": f"{b['player']} had an uncharacteristically expensive day",
                    "detail": f"Rated our most economical bowler this season (econ {b['econ']}), "
                              f"but went for {round(econ_today, 2)}/over today "
                              f"({int(r['W'])}/{int(r['R'])} off {balls_to_overs_str(balls)} overs)."}
    return None


def verdict_weak_bowler_right(match, bowl, them_weak):
    for b in them_weak:
        sub = bowl[(bowl["matchId"] == match["matchId"]) & (bowl["team"] == match["opponent"]) & (bowl["bowlerClean"] == b["player"])]
        if sub.empty:
            continue
        r = sub.iloc[0]
        balls = overs_to_balls(r["O"])
        if balls == 0:
            continue
        econ_today = r["R"] / (balls / 6)
        if econ_today >= b["econ"] + ECON_MARGIN:
            return {"title": f"Cashed in on {b['player']}, exactly as flagged",
                    "detail": f"One of their weakest bowlers this season (econ {b['econ']}) — "
                              f"went for {round(econ_today, 2)}/over against us today."}
    return None


def verdict_weak_bowler_wrong(match, bowl, them_weak):
    for b in them_weak:
        sub = bowl[(bowl["matchId"] == match["matchId"]) & (bowl["team"] == match["opponent"]) & (bowl["bowlerClean"] == b["player"])]
        if sub.empty:
            continue
        r = sub.iloc[0]
        balls = overs_to_balls(r["O"])
        if balls == 0:
            continue
        econ_today = r["R"] / (balls / 6)
        if econ_today <= b["econ"] - ECON_MARGIN:
            return {"title": f"Let {b['player']} off the hook",
                    "detail": f"Flagged as one of their weakest bowlers this season (econ "
                              f"{b['econ']}), but bowled at {round(econ_today, 2)}/over against us "
                              f"today — better than his norm."}
    return None


def verdict_bowling_weakness_right(match, bowl, them_weak, weakness_pool):
    """Broader than the named-weak-bowler check above: looks at whoever conceded the highest
    economy for the opposition this match (min 2 overs bowled). Skips anyone already one of the
    3 explicitly flagged weakest bowlers — that's verdict_weak_bowler_right's job, and covering
    the same bowler twice would just be a duplicate bullet — and only speaks up for someone
    outside that list if his season economy independently marks him as below the league average
    too, so this doesn't just restate "he had one expensive day" as a season-long pattern that
    isn't really there. Plus, when the team's overall extras this match are notably high next to
    their own season rate, folds that in as supporting context, same two-part shape as the
    manual recap this feature was modeled on."""
    sub = bowl[(bowl["matchId"] == match["matchId"]) & (bowl["team"] == match["opponent"])].copy()
    if sub.empty:
        return None
    sub["balls"] = sub["O"].apply(overs_to_balls)
    sub = sub[sub["balls"] >= 12]
    if sub.empty:
        return None
    sub["econToday"] = sub["R"] / (sub["balls"] / 6)
    worst = sub.loc[sub["econToday"].idxmax()]
    player = worst["bowlerClean"]
    if player in {b["player"] for b in them_weak}:
        return None
    season_row = weakness_pool[(weakness_pool["team"] == match["opponent"]) & (weakness_pool["player"] == player)] \
        if not weakness_pool.empty else weakness_pool
    season_econ = float(season_row.iloc[0]["econ"]) if not season_row.empty else None
    if season_econ is None or worst["econToday"] < season_econ + ECON_MARGIN:
        return None
    league_avg_econ = weakness_pool["econ"].mean() if not weakness_pool.empty else None
    if league_avg_econ is None or season_econ <= league_avg_econ:
        return None

    detail = (f"{player} went for {int(worst['R'])} off {balls_to_overs_str(int(worst['balls']))} "
              f"(econ {round(worst['econToday'], 2)}), the most expensive spell of the match — "
              f"consistent with him not being one of their trusted bowlers.")
    team_bowl = bowl[bowl["team"] == match["opponent"]].copy()
    team_bowl["extras"] = team_bowl["wides"] + team_bowl["noballs"]
    per_match_extras = team_bowl.groupby("matchId")["extras"].sum()
    this_match_extras = int(sub["wides"].sum() + sub["noballs"].sum())
    if len(per_match_extras) >= 5 and this_match_extras >= per_match_extras.mean() + 3:
        wd, nb = int(sub["wides"].sum()), int(sub["noballs"].sum())
        nb_part = f" + {nb} no-ball{'s' if nb != 1 else ''}" if nb else ""
        detail += (f" Their attack also leaked {wd} wide{'s' if wd != 1 else ''}{nb_part} "
                   f"({this_match_extras} extras) to us, matching the extras-prone profile we'd "
                   f"flagged for their bowling unit generally.")
    return {"title": "Their bowling weaknesses tracked", "detail": detail}


def ai_insight_followthrough(insights, match, bat, bowl, gladiators, gladiators_overs):
    """For each of this season's (up to 3) AI insights, checks whether it was actionable this
    match (the player it's about actually took the field) and, if so, whether the
    recommendation was followed and what happened — kept separate from the right/wrong verdicts
    above because the outcome here is often genuinely mixed ('followed, but didn't pay off
    today'), not a clean hit or miss the way those are."""
    out = []
    for insight in insights:
        itype, player = insight.get("type"), insight.get("player")

        if itype == "battingOrder":
            sub = bat[(bat["matchId"] == match["matchId"]) & (bat["team"] == gladiators)].reset_index(drop=True)
            idx = sub.index[sub["playerClean"] == player]
            if idx.empty:
                out.append({"title": insight["title"], "actionable": False,
                            "detail": f"{player} didn't bat for us today, so this recommendation wasn't in play."})
                continue
            position = int(idx[0]) + 1
            row = sub.loc[idx[0]]
            runs, balls = int(row["R"]), int(row["B"])
            season_pos = insight.get("seasonAvgPosition")
            followed = season_pos is not None and position < season_pos - 0.5
            if followed:
                if runs >= 20:
                    detail = (f"He batted at #{position} (up from his {season_pos:.1f} season-average "
                              f"position, matching our insight) and it paid off — {runs} ({balls}b).")
                else:
                    score_desc = f"a {balls}-ball duck" if runs == 0 else f"{runs} ({balls}b)"
                    tail = " — though it cost nothing given the final margin." if match["result"] == "Win" else ""
                    detail = (f"He batted at #{position} (up from his {season_pos:.1f} season-average "
                              f"position, matching our insight), but was out for {score_desc}. Correct "
                              f"process, bad individual outcome{tail}")
            else:
                detail = (f"He batted at #{position} today" +
                          (f" — about the same as his {season_pos:.1f} season-average position, so "
                           f"this one wasn't really acted on." if season_pos is not None else "."))
            out.append({"title": insight["title"], "actionable": True, "followed": followed, "detail": detail})

        elif itype == "phaseBowling":
            if gladiators_overs is None:
                out.append({"title": insight["title"], "actionable": False,
                            "detail": "Over-by-over data isn't available for this match."})
                continue
            lo, hi = insight["phaseBounds"]
            match_overs = gladiators_overs[
                (gladiators_overs["matchId"] == match["matchId"]) & (gladiators_overs["bowlerResolved"] == player)
            ]
            phase_overs = match_overs[(match_overs["overNum"] >= lo) & (match_overs["overNum"] <= hi)]
            if phase_overs.empty:
                detail = (f"{player} didn't bowl in {insight['phaseLabel'].lower()} today" +
                          (" (though he did bowl elsewhere in the innings)." if not match_overs.empty else "."))
                out.append({"title": insight["title"], "actionable": not match_overs.empty,
                            "followed": False, "detail": detail})
                continue
            legal_balls = int(phase_overs["legalBalls"].sum())
            runs = int(phase_overs["runs"].sum())
            econ = round(runs / (legal_balls / 6), 2) if legal_balls else None
            detail = (f"He bowled {len(phase_overs)} over(s) in {insight['phaseLabel'].lower()} today "
                      f"(econ {econ}) — the recommendation was followed.")
            out.append({"title": insight["title"], "actionable": True, "followed": True, "detail": detail})

        elif itype == "bowlingWorkload":
            sub = bowl[(bowl["matchId"] == match["matchId"]) & (bowl["team"] == gladiators) & (bowl["bowlerClean"] == player)]
            if sub.empty:
                out.append({"title": insight["title"], "actionable": False,
                            "detail": f"{player} didn't bowl for us today, so this recommendation wasn't in play."})
                continue
            r = sub.iloc[0]
            balls = overs_to_balls(r["O"])
            followed = balls >= 18  # 3+ overs of a 4-over max allotment
            econ = round(r["R"] / (balls / 6), 2) if balls else None
            detail = (f"He bowled {balls_to_overs_str(balls)} overs today (econ {econ})" +
                      (", a full workload — recommendation followed." if followed
                       else ", still on the light side for someone we'd want bowling more."))
            out.append({"title": insight["title"], "actionable": True, "followed": followed, "detail": detail})
    return out


def build_match_recap(bat, bowl, results, gladiators, teams_data, ai_insights, gladiators_overs,
                       weakness_pool, league_stats):
    """Post-match 'what we got right / wrong' plus Star of the Match for the latest completed
    match, or None if this team hasn't played yet. Each right/wrong bucket is capped at 3 and
    never padded — a quiet match with no clear signal just returns fewer."""
    match = latest_completed_match(results, gladiators)
    if match is None:
        return None
    them = teams_data[match["opponent"]]
    us_strengths = teams_data[gladiators]["bowlingStrengths"]

    right_generators = [
        lambda: verdict_toss_right(match, them["toss"]),
        lambda: verdict_par_target_right(match, them["parTarget"]),
        lambda: verdict_key_batsman_right(match, bat, them),
        lambda: verdict_bowling_strength_right(match, bowl, gladiators, us_strengths),
        lambda: verdict_weak_bowler_right(match, bowl, them["weakBowlers"]),
        lambda: verdict_bowling_weakness_right(match, bowl, them["weakBowlers"], weakness_pool),
    ]
    wrong_generators = [
        lambda: verdict_toss_wrong(match, them["toss"]),
        lambda: verdict_par_target_wrong(match, them["parTarget"]),
        lambda: verdict_key_batsman_wrong(match, bat, them),
        lambda: verdict_bowling_strength_wrong(match, bowl, gladiators, us_strengths),
        lambda: verdict_weak_bowler_wrong(match, bowl, them["weakBowlers"]),
    ]
    right = [r for r in (g() for g in right_generators) if r is not None][:3]
    wrong = [r for r in (g() for g in wrong_generators) if r is not None][:3]

    points = match_points_table(bat, bowl, match["matchId"], gladiators, league_stats)
    star = points[0] if points else None

    followthrough = ai_insight_followthrough(ai_insights, match, bat, bowl, gladiators, gladiators_overs)

    return {
        "matchId": match["matchId"], "opponent": match["opponent"], "result": match["result"],
        "date": match["date"],
        "gladiatorsScore": match["teamScore"], "opponentScore": match["oppScore"],
        "battedFirst": match["battedFirst"],
        "right": right, "wrong": wrong,
        "starOfMatch": star, "pointsTable": points,
        "insightFollowthrough": followthrough,
    }


def season_star_leaderboard(bat, bowl, results, gladiators, league_stats):
    """'Star of the tournament so far' — each Gladiators player's Star of the Match impact score
    (same z-scored formula, see league_points_stats) summed across every completed match this
    season. Ranked by total, not per-match average: a tournament-long standout is about total
    contribution delivered over the season, not efficiency in a small sample, same reasoning as
    why real player-of-the-series awards go to cumulative impact rather than a rate stat."""
    match_ids = sorted(results[results["team"] == gladiators]["matchId"].unique())
    totals = {}
    for match_id in match_ids:
        rows = match_points_table(bat, bowl, int(match_id), gladiators, league_stats)
        for i, r in enumerate(rows):
            entry = totals.setdefault(r["player"], {
                "player": r["player"], "totalImpact": 0.0, "matches": 0, "motmCount": 0,
            })
            entry["totalImpact"] += r["impactScore"]
            entry["matches"] += 1
            if i == 0:
                entry["motmCount"] += 1
    rows = list(totals.values())
    for r in rows:
        r["totalImpact"] = round(r["totalImpact"], 2)
        r["avgImpact"] = round(r["totalImpact"] / r["matches"], 2)
    rows.sort(key=lambda r: -r["totalImpact"])
    return rows


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


def full_standings_table(cfg):
    """Every team in every group, in rank order — the raw material for a standalone
    standings page. Unlike load_points_table() (a team -> row dict used to annotate a
    single opponent's own record), this keeps every team and preserves group structure,
    since a standings page needs to show the whole table, not just one team's line."""
    pts = pd.read_csv(DATA_DIR / cfg["points_csv"])
    groups = []
    for group, g in pts.groupby("group", sort=True):
        rows = []
        for _, r in g.sort_values("rank").iterrows():
            pts_match = re.match(r"-?\d+", str(r["pts"]))
            rows.append({
                "rank": int(r["rank"]), "team": r["team"].strip(),
                "mat": int(r["mat"]), "won": int(r["won"]), "lost": int(r["lost"]),
                "tie": int(r["tie"]), "nr": int(r["nr"]),
                "pts": int(pts_match.group()) if pts_match else None,
                "winPct": float(str(r["winpct"]).rstrip("%")),
                "netRR": float(r["netrr"]),
            })
        groups.append({"group": group, "rows": rows})
    return groups


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


def load_upcoming(cfg, team, results):
    """All remaining scheduled matches for `team` that haven't been played yet, soonest first.
    The dashboard shows the first 3 highlighted with the rest behind a "show all" toggle — no
    cap here so that toggle has real data to expand into.

    A pure date-vs-today cutoff isn't enough on its own: a match played earlier today is
    already done, but the calendar day hasn't rolled over yet, so it'd still pass a ">= today"
    filter and wrongly show as upcoming (caught 2026-08-15/16: exactly this). So on top of the
    date filter, also drop any schedule row that already has a matching completed result for
    this team — same opponent, same date (results' 'date' column comes from attach_venue()'s
    schedule matching, already run by the time this is called)."""
    df = pd.read_excel(DATA_DIR / cfg["schedule_xlsx"], header=1)
    df = df[(df["Team One"] == team) | (df["Team Two"] == team)].copy()
    df["parsedDate"] = pd.to_datetime(df["Date"], format="%m/%d/%Y", errors="coerce")
    df["opponent"] = df.apply(lambda r: r["Team Two"] if r["Team One"] == team else r["Team One"], axis=1)

    played = {
        (r["opponent"], r["date"])
        for _, r in results[results["team"] == team].iterrows() if pd.notna(r.get("date"))
    }

    # date-only comparison — TODAY carries a time-of-day (datetime.now()) but schedule dates are
    # midnight-only, so comparing full datetimes would incorrectly drop a match scheduled for
    # later today the moment the clock passes midnight.
    upcoming = df[df["parsedDate"] >= pd.Timestamp(TODAY.date())].sort_values("parsedDate")
    out = []
    for _, r in upcoming.iterrows():
        opponent = r["opponent"]
        if (opponent, r["parsedDate"].strftime("%b %d, %Y")) in played:
            continue
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

        upcoming = load_upcoming(cfg, gladiators, results)
        print(f"  upcoming: {len(upcoming)}")

        standings = load_points_table(cfg)
        standings_table = full_standings_table(cfg)
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

        gladiators_overs = load_gladiators_overs(cfg, gladiators, abbrev_map)
        death_overs = death_overs_only(gladiators_overs)
        death_leaders = death_overs_leaders(death_overs)
        print(f"  death-overs data: {'none scraped yet' if death_overs is None else f'{len(death_overs)} death-over rows, {len(death_leaders)} qualifying bowlers'}")
        bowler_phases = bowler_phase_breakdown(gladiators_overs)
        print(f"  bowler-by-phase: {sum(len(p['bowlers']) for p in bowler_phases)} qualifying bowler-phase entries across {len(bowler_phases)} phases")

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
                "recentResults": team_recent_form(results, team),
                "keyBatsmanWinImpact": (
                    key_batsman_win_impact(bat, results, team, top_bat[0]["player"])
                    if top_bat else None
                ),
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
        best_xi = best_playing_xi(bat, bowl, bat_strength_pool, strength_pool, gladiators)
        league_avg_collapse_pct = (
            round(sum(t["battingCollapses"]["collapsePct"] for t in teams_data.values()) / len(teams_data))
            if teams_data else 0
        )
        bowling_leaderboard = team_bowling_agg(bowl, gladiators).to_dict("records")
        ai_insights = build_ai_insights(
            bowler_phases, best_xi["roster"], batting_position_avg(bat, gladiators),
            teams_data[gladiators]["bowlingStrengths"], bowling_leaderboard,
        )
        league_stats = league_points_stats(bat, bowl)
        star_leaderboard = season_star_leaderboard(bat, bowl, results, gladiators, league_stats)
        gladiators_charts = {
            "bestXI": best_xi,
            "eloHistory": gladiators_elo_history,
            "battingLeaderboard": team_batting_agg(bat, gladiators).to_dict("records"),
            "bowlingLeaderboard": bowling_leaderboard,
            "leagueAvgCollapsePct": league_avg_collapse_pct,
            "winDependency": win_dependency(bat, bowl, results, gladiators),
            "bowlerPhases": bowler_phases,
            "aiInsights": ai_insights,
            "starLeaderboard": star_leaderboard,
        }
        print(f"  best XI: {len(best_xi['players'])} players from a qualifying squad of {best_xi['squadSize']}")
        print(f"  AI insights: {len(ai_insights)}")
        print(f"  star leaderboard: {len(star_leaderboard)} players across {len(results[results['team'] == gladiators])} matches")

        match_recap = build_match_recap(bat, bowl, results, gladiators, teams_data,
                                         ai_insights, gladiators_overs, weakness_pool, league_stats)
        if match_recap is None:
            print("  match recap: no completed matches yet")
        else:
            star_name = match_recap["starOfMatch"]["player"] if match_recap["starOfMatch"] else None
            print(f"  match recap: {len(match_recap['right'])} right, {len(match_recap['wrong'])} wrong, star={star_name}")

        out["series"][key] = {
            "label": cfg["label"], "gladiators": gladiators,
            "opponents": opponents, "upcoming": upcoming, "teams": teams_data,
            "deathOversLeaders": death_leaders, "gladiatorsCharts": gladiators_charts,
            "matchRecap": match_recap, "standingsTable": standings_table,
        }

    js = "// Auto-generated by build_data.py — do not edit by hand.\nconst NJSBCL_DATA = " + json.dumps(out, indent=None) + ";\n"
    OUT_FILE.write_text(js)
    print(f"Wrote {OUT_FILE} ({OUT_FILE.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    build()
