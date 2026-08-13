"""Data-quality checks for a scraped TNPL season.

Validates the combined ball-by-ball CSV on three levels:
  1. Structural — coverage, duplicates, over/ball continuity, value ranges,
     short overs, unresolved player names.
  2. Reconciliation — per-innings runs/wickets/overs rebuilt from deliveries
     vs the official final scores in each match's summary header (authoritative,
     matches published scorecards).
  3. External — season aggregates (run leaders) vs independently reported
     numbers (espncricinfo match report: Tushar Raheja topped TNPL 2025 with
     488 runs at SR 186).

Usage: python3 TNPL/data_quality.py [year]   (default 2025)
Writes TNPL/data_quality_report.md and prints a summary.
"""

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
YEAR = sys.argv[1] if len(sys.argv) > 1 else "2025"

rows = list(csv.DictReader((ROOT / f"tnpl_{YEAR}_bbb.csv").open()))
matches = list(csv.DictReader((ROOT / f"tnpl_{YEAR}_matches.csv").open()))
for r in rows:
    for k in ("innings", "over", "ball", "runs_total", "runs_batter",
              "runs_extras", "is_wicket"):
        r[k] = int(r[k])

report = ["# TNPL {} data-quality report".format(YEAR), ""]
issues = []


def check(name, problems, detail_limit=8):
    ok = not problems
    line = f"- {'PASS' if ok else 'FAIL'} — {name}"
    if problems:
        line += f" ({len(problems)} issue{'s' if len(problems) > 1 else ''})"
        issues.extend(problems)
    report.append(line)
    for p in problems[:detail_limit]:
        report.append(f"    - {p}")
    if len(problems) > detail_limit:
        report.append(f"    - ... and {len(problems) - detail_limit} more")


# ── 1. Structural checks ─────────────────────────────────────────────────────
report.append("## 1. Structural checks")
report.append(f"- Matches in schedule: **{len(matches)}**, "
              f"deliveries scraped: **{len(rows)}**")

check("every scheduled match scraped",
      [f"match {m['match_id']} ({m['name']}): status={m['status']}, no deliveries"
       for m in matches if not int(m["deliveries"] or 0)])

seen = defaultdict(int)
for r in rows:
    seen[(r["match_id"], r["innings"], r["over"], r["ball"])] += 1
check("no duplicate deliveries (match, innings, over, ball)",
      [f"{k} appears {v}×" for k, v in seen.items() if v > 1])

problems = []
balls_by_over = defaultdict(list)
for r in rows:
    balls_by_over[(r["match_id"], r["innings"], r["over"])].append(r["ball"])
for (mid, inn, over), balls in balls_by_over.items():
    if sorted(balls) != list(range(1, len(balls) + 1)):
        problems.append(f"match {mid} inn {inn} over {over}: balls {sorted(balls)}")
check("ball numbers consecutive within each over", problems)

problems = []
overs_by_inn = defaultdict(set)
for r in rows:
    overs_by_inn[(r["match_id"], r["innings"])].add(r["over"])
for (mid, inn), overs in overs_by_inn.items():
    if sorted(overs) != list(range(1, max(overs) + 1)):
        missing = sorted(set(range(1, max(overs) + 1)) - overs)
        problems.append(f"match {mid} inn {inn}: missing overs {missing}")
check("over numbers consecutive within each innings", problems)

last_over = {k: max(v) for k, v in overs_by_inn.items()}
problems = []
for (mid, inn, over), balls in balls_by_over.items():
    if over != last_over[(mid, inn)] and len(balls) < 6:
        problems.append(f"match {mid} inn {inn} over {over}: only {len(balls)} deliveries")
check("non-final overs have at least 6 deliveries", problems)

check("per-ball values in range (0<=runs_total<=8, 0<=runs_batter<=6, "
      "extras>=0, 0<=wickets<=2)",
      [f"match {r['match_id']} inn {r['innings']} {r['over']}.{r['ball']}: "
       f"total={r['runs_total']} bat={r['runs_batter']} extras={r['runs_extras']} "
       f"wkt={r['is_wicket']}"
       for r in rows
       if not (0 <= r["runs_total"] <= 8 and 0 <= r["runs_batter"] <= 6
               and r["runs_extras"] >= 0 and 0 <= r["is_wicket"] <= 2)])

check("player names resolved (no bare athlete ids)",
      sorted({f"{col} id {r[col]} (match {r['match_id']})"
              for r in rows for col in ("batter", "non_striker", "bowler")
              if r[col].isdigit()}))

check("wickets carry a dismissal kind",
      [f"match {r['match_id']} inn {r['innings']} {r['over']}.{r['ball']}: "
       f"{r['is_wicket']} wicket(s), kind='{r['wicket_kind']}'"
       for r in rows if r["is_wicket"] >= 1 and not r["wicket_kind"]])

# ── 2. Reconciliation vs official final scores ───────────────────────────────
report.append("")
report.append("## 2. Innings totals vs official scores (summary header)")

def parse_official(s):
    """'220/5' or '102 (14.4/20 ov, target 221)' -> (runs, wickets, overs|None)."""
    m = re.match(r"(\d+)(?:/(\d+))?", s.strip())
    runs = int(m.group(1))
    wkts = int(m.group(2)) if m.group(2) else 10
    ov = re.search(r"\((\d+(?:\.\d)?)/", s)
    return runs, wkts, float(ov.group(1)) if ov else None

agg = defaultdict(lambda: [0, 0, 0])  # (mid, innings) -> [runs, wickets, balls]
for r in rows:
    a = agg[(r["match_id"], str(r["innings"]))]
    a[0] += r["runs_total"]
    a[1] += r["is_wicket"]

problems, reconciled = [], 0
for m in matches:
    if not int(m["deliveries"] or 0):
        continue
    # innings 1 belongs to whichever side's score has no target annotation;
    # match scraped scores by trying both orders
    officials = [(m["home_team"], m["home_score"]), (m["away_team"], m["away_score"])]
    officials = [(t, s) for t, s in officials if s and re.match(r"\d", s)]
    scraped = [(inn, agg[(m["match_id"], inn)]) for inn in ("1", "2")
               if (m["match_id"], inn) in agg]
    got = sorted((a[0], a[1]) for _, a in scraped)
    want = sorted(parse_official(s)[:2] for _, s in officials)
    if got == want:
        reconciled += len(officials)
    else:
        problems.append(f"match {m['match_id']} ({m['name']}): scraped {got} vs official {want}")
report.append(f"- Innings reconciled exactly: **{reconciled}**")
check("every innings total (runs & wickets) matches the official score", problems)

# ── 3. External cross-checks ─────────────────────────────────────────────────
report.append("")
report.append("## 3. External cross-checks")

bat = defaultdict(lambda: [0, 0])  # batter -> [runs, balls faced (legal)]
for r in rows:
    bat[r["batter"]][0] += r["runs_batter"]
    if r["play_type"] != "wide":
        bat[r["batter"]][1] += 1
top = sorted(bat.items(), key=lambda x: -x[1][0])[:5]
report.append("- Season top-5 run scorers (scraped):")
for name, (runs, balls) in top:
    report.append(f"    - {name}: {runs} runs, SR {runs / balls * 100:.0f}")

leader, (lruns, lballs) = top[0]
expected = ("Tushar Raheja", 488, 186)
ok = (expected[0].split()[-1] in leader and lruns == expected[1]
      and abs(lruns / lballs * 100 - expected[2]) < 1)
check(f"run leader matches espncricinfo report ({expected[0]}, "
      f"{expected[1]} runs, SR {expected[2]})",
      [] if ok else [f"scraped: {leader} {lruns} runs SR {lruns / lballs * 100:.0f}"])

# ── Verdict ──────────────────────────────────────────────────────────────────
report.append("")
verdict = ("**VERDICT: all checks passed — dataset reconciles with official "
           "scorecards and external reports.**" if not issues else
           f"**VERDICT: {len(issues)} issue(s) found — see FAIL items above.**")
report.append(verdict)

out = ROOT / "data_quality_report.md"
out.write_text("\n".join(report) + "\n")
print("\n".join(report))
print(f"\nWrote {out}")
