"""Scrape ball-by-ball data for one TNPL match from ESPN's public APIs.

ESPNcricinfo's own APIs (hs-consumer-api, /matches/engine) are bot-blocked, and
as of 2026-08-12 so is `site.api.espn.com` (Akamai 403 on every request,
including previously-working match ids — a change since this pipeline was last
run, not something specific to new matches). ESPN's core API
(`core.espnuk.org`) remains open and has everything needed:

  event:    http://core.espnuk.org/v2/sports/cricket/leagues/{league}/events/{match}
            (name, date, competitors with inline win/loss + refs to team/score)
  status:   .../competitions/{match}/status   (match state: pre/in/post)
  team:     http://core.espnuk.org/v2/sports/cricket/teams/{teamId}
  athlete:  http://core.espnuk.org/v2/sports/cricket/leagues/{league}/athletes/{athleteId}
            (player names — replaces the old summary-endpoint roster)
  plays:    .../events/{match}/competitions/{match}/plays?limit=300   (refs, one per delivery)

Each play ref resolves to a detail record with innings, over.number, over.ball,
batsman/bowler athlete ids, runs and dismissal info. Per-ball scoreValue/dismissal
undercount compound events (e.g. "no ball + 4 byes" has scoreValue 1), so runs
and wickets are derived from the batting side's running-score deltas, which
reconcile exactly with published scorecards.

Player and team names are cached in shared `raw/athletes/` and `raw/teams/`
directories (not per-match) since the same ids recur constantly across a
season's matches — keeps the extra round-trips this rewrite needs cheap after
the first few matches.

Usage: python3 TNPL/scrape_match.py [match_id]   (default: 1489138, 2025 final)
Output: TNPL/bbb_{match_id}.csv and a raw JSON cache in TNPL/raw/{match_id}/
"""

import csv
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LEAGUE = "1047323"  # TNPL umbrella league id in ESPN's core API
ROOT = Path(__file__).resolve().parent

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def get_json(url, cache_file):
    """Fetch a URL with a browser UA, caching the raw JSON to disk."""
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))
    cache_file.write_text(json.dumps(data))
    time.sleep(0.05)
    return data


def athlete_id(node):
    return node["athlete"]["$ref"].rstrip("/").rsplit("/", 1)[-1]


def score_tuple(s):
    """'102/8' -> (102, 8); '102' means all out -> (102, 10)."""
    runs, _, wkts = s.partition("/")
    return int(runs), int(wkts) if wkts else 10


_PLAYER_NAME_CACHE = {}
_TEAM_NAME_CACHE = {}


def resolve_athlete_name(athlete_id_):
    """Player name for an athlete id, cached in a shared cross-match directory
    (raw/athletes/) since ids recur across a whole season, not just one match."""
    if athlete_id_ in ("0", ""):
        return athlete_id_
    if athlete_id_ in _PLAYER_NAME_CACHE:
        return _PLAYER_NAME_CACHE[athlete_id_]
    data = get_json(
        f"http://core.espnuk.org/v2/sports/cricket/leagues/{LEAGUE}/athletes/{athlete_id_}",
        ROOT / "raw" / "athletes" / f"{athlete_id_}.json")
    name = data.get("fullName") or data.get("displayName") or athlete_id_
    _PLAYER_NAME_CACHE[athlete_id_] = name
    return name


def resolve_team_name(team_ref):
    """Team display name from a $ref, cached in a shared cross-match directory
    (raw/teams/) — a league only has ~14 teams, reused by every match."""
    team_id = team_ref.rstrip("/").rsplit("/", 1)[-1]
    if team_id in _TEAM_NAME_CACHE:
        return _TEAM_NAME_CACHE[team_id]
    data = get_json(team_ref, ROOT / "raw" / "teams" / f"{team_id}.json")
    name = data.get("displayName", "")
    _TEAM_NAME_CACHE[team_id] = name
    return name


def scrape_match(match_id, verbose=False):
    """Return (rows, meta) for one match. rows is one dict per delivery."""
    raw = ROOT / "raw" / match_id

    event = get_json(
        f"http://core.espnuk.org/v2/sports/cricket/leagues/{LEAGUE}/events/{match_id}",
        raw / "event.json")
    comp = event["competitions"][0]
    status = get_json(comp["status"]["$ref"], raw / "status.json") if "status" in comp else {}

    meta = {"match_id": match_id,
            "name": event.get("name", ""),
            "description": comp.get("description", ""),
            "date": comp.get("date", ""),
            "status": status.get("type", {}).get("state", "")}
    for c in comp.get("competitors", []):
        tag = c.get("homeAway", "")
        team_name = resolve_team_name(c["team"]["$ref"]) if "team" in c else ""
        meta[f"{tag}_team"] = team_name
        score = get_json(c["score"]["$ref"], raw / f"score_{c['id']}.json") if "score" in c else {}
        meta[f"{tag}_score"] = score.get("displayValue", "")
        if c.get("winner"):
            meta["winner"] = team_name
    meta.setdefault("winner", "")

    base = (f"http://core.espnuk.org/v2/sports/cricket/leagues/{LEAGUE}"
            f"/events/{match_id}/competitions/{match_id}/plays")
    refs, page = [], 1
    while True:
        listing = get_json(f"{base}?limit=300&page={page}", raw / f"plays_p{page}.json")
        refs += [it["$ref"] for it in listing["items"]]
        if page >= listing.get("pageCount", 1):
            break
        page += 1
    meta["deliveries"] = len(refs)
    if verbose:
        print(f"  {meta['name']}: {len(refs)} deliveries")

    def fetch(ref):
        detail_id = ref.rstrip("/").rsplit("/", 1)[-1]
        return get_json(ref, raw / f"detail_{detail_id}.json")

    with ThreadPoolExecutor(max_workers=6) as ex:
        details = list(ex.map(fetch, refs))
    details.sort(key=lambda d: (d["innings"]["number"], d["over"]["number"], d["over"]["ball"]))

    rows = []
    prev = {}  # innings -> (runs, wickets)
    for d in details:
        over, dis, inn = d["over"], d["dismissal"], d["innings"]["number"]
        # Despite the names, homeScore tracks the side batting first and
        # awayScore the side batting second, regardless of home/away
        # (verified on matches where the away team batted first).
        score = d["homeScore"] if inn % 2 == 1 else d["awayScore"]
        p_runs, p_wkts = prev.get(inn, (0, 0))
        if score and score[0].isdigit():
            runs, wkts = score_tuple(score)
        else:
            # rare empty score string (rain-affected matches): fall back to the
            # per-ball fields for this delivery only
            runs = p_runs + d["scoreValue"]
            wkts = p_wkts + int(bool(dis["dismissal"]))
            score = f"{runs}/{wkts}"
        prev[inn] = (runs, wkts)
        batter_id = athlete_id(d["batsman"])
        bowler_id = athlete_id(d["bowler"])
        runs_batter = d["batsman"].get("runs") or 0
        rows.append({
            "match_id": match_id,
            "innings": inn,
            "over": over["number"],
            "ball": over["ball"],
            "batter": resolve_athlete_name(batter_id),
            "non_striker": resolve_athlete_name(athlete_id(d["otherBatsman"])),
            "bowler": resolve_athlete_name(bowler_id),
            "runs_total": runs - p_runs,
            "runs_batter": runs_batter,
            "runs_extras": runs - p_runs - runs_batter,
            "play_type": d["playType"]["description"],
            "is_wicket": wkts - p_wkts,
            "wicket_kind": dis["type"] if dis["dismissal"] else "",
            "dismissed": resolve_athlete_name(athlete_id(dis["batsman"])) if dis["dismissal"] else "",
            "team_score": score,
        })
    return rows, meta


def main():
    match_id = sys.argv[1] if len(sys.argv) > 1 else "1489138"
    rows, meta = scrape_match(match_id, verbose=True)
    if not rows:
        print(f"No deliveries for match {match_id} (status: {meta['status']})")
        return
    out = ROOT / f"bbb_{match_id}.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {out} ({len(rows)} deliveries)")
    for inn in sorted({r["innings"] for r in rows}):
        inn_rows = [r for r in rows if r["innings"] == inn]
        runs = sum(r["runs_total"] for r in inn_rows)
        wkts = sum(r["is_wicket"] for r in inn_rows)
        print(f"  Innings {inn}: {runs}/{wkts} ({len(inn_rows)} deliveries)")


if __name__ == "__main__":
    main()
