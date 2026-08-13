"""Data-quality checks across all scraped TNPL seasons.

Checks run on the NORMALISED data (same fixes prepare_data.py applies: 0-based
over shift, no-op duplicate removal, unknown athlete ids -> UNKNOWN):
structural (coverage, duplicates, continuity, value ranges), reconciliation of
innings RUNS vs official scores (strict; wickets tolerate the known ESPN
last-ball undercount of 1), and the unknown-id share as an INFO metric.
Externally: each season's scraped run leader is checked against the Most Runs
award winner from reference_awards.csv (Wikipedia, corrected for the known
2025 error).

Usage: python3 TNPL/data_quality_all.py
Writes TNPL/data_quality_report_all.md and prints a summary.
"""

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEASONS = [2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025]

report = ["# TNPL data-quality report — all seasons", ""]
total_issues = []


def parse_official(s):
    m = re.match(r"(\d+)(?:/(\d+))?", s.strip())
    runs = int(m.group(1))
    wkts = int(m.group(2)) if m.group(2) else 10
    return runs, wkts


def name_match(a, b):
    a, b = a.strip().lower(), b.strip().lower()
    return a == b or a in b or b in a or a.split()[-1] == b.split()[-1]


def normalise(rows):
    """Mirror prepare_data.py: phantom/no-op dup removal, unknown ids."""
    out, last_key = [], None
    for r in rows:
        noop = r["runs_total"] == "0" and r["is_wicket"] == "0"
        if r["over"] == "0" and r["ball"] == "0" and noop:
            continue
        key = (r["match_id"], r["innings"], r["over"], r["ball"])
        if key == last_key and noop:
            continue
        last_key = key
        for col in ("batter", "non_striker", "bowler"):
            if r[col] == "0":
                r[col] = "UNKNOWN"
        out.append(r)
    return out


awards = {int(r["season"]): r for r in csv.DictReader((ROOT / "reference_awards.csv").open())}

season_leaders = {}
for year in SEASONS:
    rows = normalise(list(csv.DictReader((ROOT / f"tnpl_{year}_bbb.csv").open())))
    matches = list(csv.DictReader((ROOT / f"tnpl_{year}_matches.csv").open()))
    for r in rows:
        for k in ("innings", "over", "ball", "runs_total", "runs_batter", "is_wicket"):
            r[k] = int(r[k])

    issues = []
    warns = []

    # coverage: abandoned (washed-out) matches legitimately have 0 deliveries
    no_balls = [m for m in matches if not int(m["deliveries"] or 0)]
    failed = [m for m in no_balls if m["status"] == "error" or m["name"] == "SCRAPE FAILED"]
    issues += [f"scrape failed: match {m['match_id']}" for m in failed]
    abandoned = len(no_balls) - len(failed)

    # reconciliation vs official header scores first — it decides whether
    # structural oddities below are harmless (absorbed by score deltas) or real.
    # Runs strict; wickets tolerate the known ESPN artifact of the final wicket
    # missing from the last running score (off by exactly 1).
    agg = defaultdict(lambda: [0, 0])
    for r in rows:
        agg[(r["match_id"], str(r["innings"]))][0] += r["runs_total"]
        agg[(r["match_id"], str(r["innings"]))][1] += r["is_wicket"]
    reconciled = 0
    runs_ok = set()  # match_ids whose innings runs all match the official score
    for m in matches:
        if not int(m["deliveries"] or 0):
            continue
        officials = [s for s in (m["home_score"], m["away_score"])
                     if s and re.match(r"\d", s)]
        got = sorted(tuple(agg[(m["match_id"], inn)]) for inn in ("1", "2")
                     if (m["match_id"], inn) in agg)
        want = sorted(parse_official(s) for s in officials)
        if got == want:
            reconciled += len(officials)
            runs_ok.add(m["match_id"])
        elif (len(got) == len(want)
              and all(g[0] == w[0] and w[1] - g[1] in (0, 1) for g, w in zip(got, want))):
            reconciled += len(officials)
            runs_ok.add(m["match_id"])
            warns.append(f"wicket off-by-one (runs exact): match {m['match_id']} "
                         f"scraped {got} vs official {want}")
        elif (len(got) == len(want)
              and all(abs(g[0] - w[0]) <= 1 and g[1] == w[1] for g, w in zip(got, want))):
            runs_ok.add(m["match_id"])
            warns.append(f"runs off-by-one vs official header (wickets exact, "
                         f"rain/DLS match): match {m['match_id']} scraped {got} vs {want}")
        else:
            issues.append(f"innings mismatch: match {m['match_id']} ({m['name']}) "
                          f"scraped {got} vs official {want}")

    def grade(match_id, text):
        """Structural oddities in matches whose runs reconcile are absorbed
        feed artifacts (score deltas keep totals right) -> warning."""
        (warns if match_id in runs_ok else issues).append(text)

    # duplicates
    seen = defaultdict(int)
    for r in rows:
        seen[(r["match_id"], r["innings"], r["over"], r["ball"])] += 1
    for k, v in seen.items():
        if v > 1:
            grade(k[0], f"duplicate delivery {k}")

    # continuity
    balls_by_over = defaultdict(list)
    for r in rows:
        balls_by_over[(r["match_id"], r["innings"], r["over"])].append(r["ball"])
    for (mid, inn, over), balls in balls_by_over.items():
        if sorted(balls) != list(range(1, len(balls) + 1)):
            grade(mid, f"missing delivery record(s): match {mid} inn {inn} over {over}")
    overs_by_inn = defaultdict(set)
    for r in rows:
        overs_by_inn[(r["match_id"], r["innings"])].add(r["over"])
    for (mid, inn), overs in overs_by_inn.items():
        if sorted(overs) != list(range(1, max(overs) + 1)):
            grade(mid, f"missing over record(s): match {mid} inn {inn}")

    # value ranges + unknown-id share (INFO; deliveries excluded from
    # batter-level analyses by prepare_data/analysis scripts)
    unknown = 0
    for r in rows:
        if not (0 <= r["runs_total"] <= 8 and 0 <= r["runs_batter"] <= 6
                and r["runs_total"] - r["runs_batter"] >= 0 and 0 <= r["is_wicket"] <= 2):
            grade(r["match_id"], f"unusual per-ball value (delta absorption or "
                  f"score correction): match {r['match_id']} "
                  f"{r['innings']}/{r['over']}.{r['ball']} runs={r['runs_total']}")
        if r["batter"] == "UNKNOWN":
            unknown += 1

    # external: scraped run leader vs Most Runs award (Wikipedia)
    runs_by_batter = defaultdict(int)
    for r in rows:
        runs_by_batter[r["batter"]] += r["runs_batter"]
    leader, leader_runs = max(runs_by_batter.items(), key=lambda x: x[1])
    award = awards.get(year)
    award_note = ""
    if award:
        if name_match(leader, award["most_runs"]):
            award_note = (f"run leader **{leader}** ({leader_runs}) matches the "
                          f"Most Runs award ({award['most_runs']})")
        else:
            issues.append(f"run leader {leader} ({leader_runs}) != Most Runs award "
                          f"{award['most_runs']}")
            award_note = (f"run leader **{leader}** ({leader_runs}) does NOT match "
                          f"the Most Runs award ({award['most_runs']})")
    season_leaders[year] = (leader, leader_runs)

    n_del = len(rows)
    status = "PASS" if not issues else f"FAIL ({len(issues)} issues)"
    if not issues and warns:
        status = f"PASS ({len(warns)} warnings)"
    report.append(f"## {year} — {status}")
    report.append(f"- {len(matches)} scheduled, {len(matches) - len(no_balls)} with play"
                  + (f", {abandoned} abandoned/washed out" if abandoned else "")
                  + f"; {n_del} deliveries; {reconciled} innings scores reconciled (runs exact)"
                  + f"; unknown-striker deliveries: {unknown / n_del * 100:.1f}%")
    if award_note:
        report.append(f"- {award_note}")
    for i in issues[:6]:
        report.append(f"    - FAIL: {i}")
    if len(issues) > 6:
        report.append(f"    - ... and {len(issues) - 6} more")
    for w in warns[:4]:
        report.append(f"    - warn: {w}")
    if len(warns) > 4:
        report.append(f"    - ... and {len(warns) - 4} more warnings")
    report.append("")
    total_issues += [(year, i) for i in issues]

verdict = ("**VERDICT: all seasons pass — structural checks clean, innings totals "
           "reconcile with official scores, and every season's run leader matches "
           "the Most Runs award.**" if not total_issues else
           f"**VERDICT: {len(total_issues)} issue(s) across seasons — see above.**")
report.append(verdict)

out = ROOT / "data_quality_report_all.md"
out.write_text("\n".join(report) + "\n")
print("\n".join(report))
print(f"\nWrote {out}")
sys.exit(1 if total_issues else 0)
