"""Data-quality checks for the NJSBCL Scout dashboard's scraped data + build output.

Run after every rescrape, right after `build_data.py`:
    cd NJSBCL && source .venv/bin/activate && python3 dq_checks.py

Exits 0 if every check passes, 1 if anything fails. WARN lines don't fail the run but are
worth a look (e.g. an optional file that hasn't been scraped yet). This exists because a single
missing trailing newline in a CSV once caused a silent data-corruption bug (two rows glued into
one) that only surfaced as a cryptic pandas ParserError deep inside build_data.py — these checks
catch that class of problem, and a few others, right after the scrape instead.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
DASHBOARD_DIR = Path(__file__).parent / "dashboard"

SERIES = {
    "division1": {
        "label": "2026 Division 1", "gladiators": "Samudhra Gladiators",
        "bat_csv": "division1_scorecards_batting.csv", "bowl_csv": "division1_scorecards_bowling.csv",
        "totals_csv": "division1_true_totals.csv", "points_csv": "division1_points_table.csv",
        "overs_csv": "division1_gladiators_overs.csv",
    },
    "weekenders": {
        "label": "2026 Weekenders Cup", "gladiators": "VRK Gladiators",
        "bat_csv": "weekenderscup_scorecards_batting.csv", "bowl_csv": "weekenderscup_scorecards_bowling.csv",
        "totals_csv": "weekenderscup_true_totals.csv", "points_csv": "weekenderscup_points_table.csv",
        "overs_csv": "weekenderscup_gladiators_overs.csv",
    },
}

failures = []
warnings = []


def check(label, condition, detail=""):
    print(f"[{'PASS' if condition else 'FAIL'}] {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(label)


def warn(condition, label, detail=""):
    if not condition:
        print(f"[WARN] {label}" + (f" — {detail}" if detail else ""))
        warnings.append(label)


def check_csv_not_concatenated(path, expected_cols):
    """Catches the exact bug that motivated this script: appending onto a file with no
    trailing newline silently glues the new row onto the end of the old last row. A raw
    pandas.read_csv() would already throw a ParserError for this, but we want a clear message
    pointing at the cause, not a stack trace — so read the raw lines and check field counts
    ourselves first."""
    lines = path.read_text().splitlines()
    if not lines:
        return True, "empty file"
    bad_lines = [i + 1 for i, l in enumerate(lines[1:], start=1) if len(l.split(",")) < expected_cols]
    # a real field-count mismatch on a merged line is usually way more than `expected_cols` fields
    # (two rows' worth), not fewer — check for that pattern specifically since a quoted field with
    # a comma inside it can legitimately make split(",") count look "off" without being corrupted
    merged_lines = [i + 1 for i, l in enumerate(lines[1:], start=1) if len(l.split(",")) > expected_cols * 1.5]
    if merged_lines:
        return False, f"line(s) {merged_lines[:5]} look like two rows merged into one (missing newline?)"
    return True, ""


for key, cfg in SERIES.items():
    print(f"\n=== {key} ({cfg['label']}) ===")

    totals_path = DATA_DIR / cfg["totals_csv"]
    bat_path = DATA_DIR / cfg["bat_csv"]
    bowl_path = DATA_DIR / cfg["bowl_csv"]
    points_path = DATA_DIR / cfg["points_csv"]
    overs_path = DATA_DIR / cfg["overs_csv"]

    for path, ncols in [(totals_path, 5), (bat_path, 9), (bowl_path, 11)]:
        if not path.exists():
            check(f"{path.name} exists", False)
            continue
        ok, detail = check_csv_not_concatenated(path, ncols)
        check(f"{path.name} has no merged/corrupted rows", ok, detail)

    if not (totals_path.exists() and bat_path.exists() and bowl_path.exists() and points_path.exists()):
        print("  (skipping remaining checks — a required file is missing)")
        continue

    totals = pd.read_csv(totals_path)
    bat = pd.read_csv(bat_path)
    bowl = pd.read_csv(bowl_path)
    points = pd.read_csv(points_path)

    check("true_totals: no duplicate matchIds", totals["matchId"].is_unique,
          f"duplicates: {sorted(totals.loc[totals['matchId'].duplicated(), 'matchId'].unique().tolist())}")
    check("true_totals: matchIds are all positive", (totals["matchId"] > 0).all())
    check("true_totals: scores are non-negative", (totals[["score1", "score2"]] >= 0).all().all())
    check("true_totals: wickets are in [0, 11]",
          totals["wkts1"].between(0, 11).all() and totals["wkts2"].between(0, 11).all())

    def duplicate_severity(df, name_col, threshold=3):
        """A handful of isolated (matchId, team) duplicates on 1-2 names is consistent
        with a genuine bowling second spell or a rare same-name-different-player
        collision — both confirmed to actually occur in this data (see
        aggregate_bowling_spells() in build_data.py, and weekenders matchId 19417's two
        different real players both named "Jithin Varghese"). `threshold`+ distinct
        names duplicated for the same (matchId, team) instead looks like the whole
        scorecard got appended twice — that's the dangerous case worth failing on."""
        dupe_mask = df.duplicated(subset=["matchId", "team", name_col])
        dupes = df.loc[dupe_mask, ["matchId", "team", name_col]].drop_duplicates()
        counts = dupes.groupby(["matchId", "team"]).size()
        return counts[counts >= threshold], counts[counts < threshold]

    bat_bad, bat_mild = duplicate_severity(bat, "player")
    check("scorecards_batting: no signs of a whole match double-scraped", bat_bad.empty,
          f"matchId+team with 3+ duplicated players: {list(bat_bad.index)}")
    warn(bat_mild.empty, "scorecards_batting has isolated player-name duplicates",
         f"{list(bat_mild.index)} — likely a same-name-different-player collision "
         f"(confirmed to happen, e.g. weekenders 19417 'Jithin Varghese'); spot check "
         f"the live scorecard before assuming corruption")

    bowl_bad, bowl_mild = duplicate_severity(bowl, "bowler")
    check("scorecards_bowling: no signs of a whole match double-scraped", bowl_bad.empty,
          f"matchId+team with 3+ duplicated bowlers: {list(bowl_bad.index)}")
    warn(bowl_mild.empty, "scorecards_bowling has isolated bowler-name duplicates",
         f"{list(bowl_mild.index)} — likely a genuine second spell (build_data.py's "
         f"aggregate_bowling_spells() combines these) or a rare name collision; spot "
         f"check the live scorecard if unsure")

    bat_matches = set(bat["matchId"].unique())
    totals_matches = set(totals["matchId"].unique())
    missing_from_totals = bat_matches - totals_matches
    gap_pct = 100 * len(missing_from_totals) / max(1, len(bat_matches))
    check("scorecards vs true-totals: matchId gap is small (<=15%, i.e. mostly abandoned matches)",
          gap_pct <= 15,
          f"{len(missing_from_totals)} of {len(bat_matches)} scorecard matches missing from true_totals ({gap_pct:.1f}%)")

    bat_teams = set(bat["team"].str.strip())
    points_teams = set(points["team"].str.strip())
    missing_teams = bat_teams - points_teams
    check("every team in scorecards also appears in the points table", not missing_teams,
          f"missing: {sorted(missing_teams)}")
    check(f"{cfg['gladiators']} present in scorecards", cfg["gladiators"] in bat_teams)

    bowl["balls"] = bowl["O"].apply(lambda o: int(o) * 6 + round((o - int(o)) * 10) if pd.notna(o) else 0)
    zero_ball_rows = bowl[(bowl["balls"] == 0) & (bowl["R"] > 0)]
    check("bowling: no rows with 0 balls bowled but runs conceded (parsing artifact)", zero_ball_rows.empty,
          f"{len(zero_ball_rows)} suspect row(s), e.g. matchId {zero_ball_rows['matchId'].iloc[0] if not zero_ball_rows.empty else ''}")

    if overs_path.exists():
        overs = pd.read_csv(overs_path)
        detail_cols = ["legalBalls", "dots", "wickets", "wides", "noballs"]
        has_detail = all(c in overs.columns for c in detail_cols)
        check("gladiators_overs.csv has ball-by-ball detail columns (not just the older runs-only format)",
              has_detail, f"columns present: {list(overs.columns)}")
        if has_detail:
            non6 = overs[overs["legalBalls"] != 6]
            pct = 100 * len(non6) / max(1, len(overs))
            check("gladiators_overs.csv: legalBalls==6 for the vast majority of rows (<=10% exceptions "
                  "expected — innings ending mid-over)", pct <= 10,
                  f"{len(non6)} of {len(overs)} rows ({pct:.1f}%) don't have exactly 6 legal balls")
    else:
        warn(False, f"{cfg['overs_csv']} not found",
             "death-overs / bowler-by-phase / two of the three AI insights will be empty for this series")

# ── data.js: was the last build_data.py run clean, and did every feature actually populate? ──
data_js_path = DASHBOARD_DIR / "data.js"
if not data_js_path.exists():
    check("dashboard/data.js exists", False)
else:
    raw = data_js_path.read_text()
    m = re.search(r"const NJSBCL_DATA = (.*);\s*$", raw.split("\n", 1)[1], re.S)
    try:
        data = json.loads(m.group(1)) if m else None
    except json.JSONDecodeError as e:
        data = None
        check("data.js parses as valid JSON", False, str(e))
    if data is not None:
        check("data.js parses as valid JSON", True)
        print("\n=== data.js feature coverage ===")
        for key, cfg in SERIES.items():
            s = data["series"].get(key)
            check(f"{key}: series present in data.js", s is not None)
            if s is None:
                continue
            gc = s["gladiatorsCharts"]
            check(f"{key}: bestXI has 11 players (or a documented squad shortfall)",
                  len(gc["bestXI"]["players"]) <= 11 and len(gc["bestXI"]["players"]) > 0)
            warn(len(gc["bowlerPhases"]) > 0 and any(p["bowlers"] for p in gc["bowlerPhases"]),
                 f"{key}: bowlerPhases is empty",
                 "expected if gladiators_overs.csv is missing/stale — see WARN above")
            warn(len(s["deathOversLeaders"]) > 0, f"{key}: deathOversLeaders is empty", "same cause as above")
            warn(len(gc["aiInsights"]) > 0, f"{key}: aiInsights produced 0 insights",
                 "not necessarily wrong (insights are never padded), but worth a manual glance")
            warn(s["matchRecap"] is not None, f"{key}: matchRecap is None", "no completed matches yet, or a bug")
            check(f"{key}: upcoming fixtures list is non-empty", len(s["upcoming"]) > 0)

print(f"\n{len(failures)} failing check(s), {len(warnings)} warning(s).")
if failures:
    sys.exit(1)
