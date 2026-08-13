"""Combine the per-season TNPL scrapes into one analysis-ready ball-by-ball CSV.

Mirrors the derived fields of the IPL pipeline (data/processed/ball_by_ball.parquet):

  batting_position  crease-arrival order per innings, tracked from both the
                    striker and non_striker so a non-striking batter who enters
                    before facing a ball keeps their true position
  phase             over 1-6 = powerplay, 7-15 = middle, 16-20 = death
  match_stage       'league' or the playoff round (Qualifier/Eliminator/Final...)
  batting_team      striker's team, resolved from the match's roster cache
  extras_type       'wide' for wides (balls faced exclude wides, as in the IPL data)

Usage:  python3 TNPL/prepare_data.py
Output: TNPL/tnpl_ball_by_ball.csv (all seasons combined)
"""

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEASONS = sorted(int(p.stem.split("_")[1]) for p in ROOT.glob("tnpl_*_bbb.csv"))

LEAGUE_RE = re.compile(r"^\d+(st|nd|rd|th) Match", re.I)


def match_stage(description):
    """'11th Match' -> league; 'Qualifier 1 (N)', 'Final', 'Eliminator' -> playoff name."""
    desc = description.split(",")[0].strip()
    if LEAGUE_RE.match(desc):
        return "league"
    return re.sub(r"\s*\(N\)$", "", desc).strip().lower() or "league"


def player_team_map(match_id):
    summary_path = ROOT / "raw" / match_id / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        m = {}
        for side in summary.get("rosters", []):
            for p in side["roster"]:
                a = p["athlete"]
                m[a["fullName"] or a["displayName"]] = side["team"]["displayName"]
        return m

    # 2026+ matches have no summary.json — site.api.espn.com is now Akamai
    # blocked (see scrape_match.py), so that endpoint is no longer scraped.
    # Derive the same player -> team mapping from the cached per-ball detail
    # JSONs instead: each delivery's batsman/otherBatsman already carries a
    # team ref, and scrape_match.py's shared raw/athletes/ + raw/teams/
    # caches already have the name lookups for both ids.
    m = {}
    athletes_dir, teams_dir = ROOT / "raw" / "athletes", ROOT / "raw" / "teams"
    for f in (ROOT / "raw" / match_id).glob("detail_*.json"):
        d = json.loads(f.read_text())
        for side in ("batsman", "otherBatsman"):
            node = d.get(side)
            if not node:
                continue
            athlete_id = node["athlete"]["$ref"].rstrip("/").rsplit("/", 1)[-1]
            team_id = node["team"]["$ref"].rstrip("/").rsplit("/", 1)[-1]
            athlete_file, team_file = athletes_dir / f"{athlete_id}.json", teams_dir / f"{team_id}.json"
            if athlete_id == "0" or not athlete_file.exists() or not team_file.exists():
                continue
            a = json.loads(athlete_file.read_text())
            name = a.get("fullName") or a.get("displayName") or athlete_id
            m[name] = json.loads(team_file.read_text()).get("displayName", "")
    return m


def normalise(rows):
    """Feed fixes: drop phantom (over 0, ball 0) no-op records and no-op
    duplicate records, blank out unknown athlete ids ('0')."""
    out, last_key = [], None
    for r in rows:
        noop = r["runs_total"] == "0" and r["is_wicket"] == "0"
        if r["over"] == "0" and r["ball"] == "0" and noop:
            continue  # phantom pre-innings record (rain-affected matches)
        key = (r["match_id"], r["innings"], r["over"], r["ball"])
        if key == last_key and noop:
            continue  # duplicate record with no score change
        last_key = key
        for col in ("batter", "non_striker", "bowler"):
            if r[col] == "0":
                r[col] = "UNKNOWN"
        out.append(r)
    return out


out_rows = []
for season in SEASONS:
    matches = {m["match_id"]: m
               for m in csv.DictReader((ROOT / f"tnpl_{season}_matches.csv").open())}
    rows = normalise(list(csv.DictReader((ROOT / f"tnpl_{season}_bbb.csv").open())))

    # batting position: crease-arrival order per (match, innings)
    arrival = {}
    for r in rows:
        key = (r["match_id"], r["innings"])
        seen = arrival.setdefault(key, {})
        for name in (r["batter"], r["non_striker"]):
            if name != "UNKNOWN" and name not in seen:
                seen[name] = len(seen) + 1

    teams = {mid: player_team_map(mid) for mid in matches}
    for r in rows:
        over = int(r["over"])
        meta = matches[r["match_id"]]
        out_rows.append({
            "season": season,
            "match_id": r["match_id"],
            "date": meta["date"][:10],
            "match_stage": match_stage(meta["description"]),
            "batting_team": teams[r["match_id"]].get(r["batter"], ""),
            "innings": int(r["innings"]),
            "over": over,
            "ball": int(r["ball"]),
            "batter": r["batter"],
            "non_striker": r["non_striker"],
            "bowler": r["bowler"],
            "runs_batter": int(r["runs_batter"]),
            "runs_extras": int(r["runs_extras"]),
            "runs_total": int(r["runs_total"]),
            "is_wicket": int(r["is_wicket"]),
            "wicket_kind": r["wicket_kind"],
            "batting_position": arrival[(r["match_id"], r["innings"])].get(r["batter"], 0),
            "phase": "powerplay" if over <= 6 else ("middle" if over <= 15 else "death"),
            "extras_type": "wide" if r["play_type"] == "wide" else "",
        })

out = ROOT / "tnpl_ball_by_ball.csv"
with out.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=out_rows[0].keys())
    w.writeheader()
    w.writerows(out_rows)

n_matches = len({r["match_id"] for r in out_rows})
inn_vals = sorted({r["innings"] for r in out_rows})
unknown = sum(1 for r in out_rows if r["batter"] == "UNKNOWN")
stages = sorted({r["match_stage"] for r in out_rows})
print(f"Wrote {out}: {len(out_rows)} deliveries, {n_matches} matches, "
      f"{len(SEASONS)} seasons")
print(f"innings values: {inn_vals} | unknown-striker deliveries: {unknown} "
      f"({unknown / len(out_rows) * 100:.1f}%)")
print(f"match stages: {stages}")
