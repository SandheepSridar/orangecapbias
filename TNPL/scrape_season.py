"""Scrape every TNPL match of a season into one combined ball-by-ball CSV.

Match ids come from the season's series id (2025 = 1489106), discoverable via
core.espnuk.org/v2/sports/cricket/leagues/1047323/seasons. The ?dates={year}
filter is required — without it the events endpoint returns only the most
recent match.

Usage: python3 TNPL/scrape_season.py [series_id year]   (default: 1489106 2025)
Output: TNPL/tnpl_{year}_bbb.csv, TNPL/tnpl_{year}_matches.csv
"""

import csv
import sys
import time
from pathlib import Path

from scrape_match import ROOT, get_json, scrape_match

SERIES = sys.argv[1] if len(sys.argv) > 1 else "1489106"
YEAR = sys.argv[2] if len(sys.argv) > 2 else "2025"

listing = get_json(
    f"http://core.espnuk.org/v2/sports/cricket/leagues/{SERIES}/events?dates={YEAR}&limit=300",
    ROOT / "raw" / f"events_{SERIES}_{YEAR}.json")
match_ids = sorted(it["$ref"].rstrip("/").rsplit("/", 1)[-1] for it in listing["items"])
print(f"TNPL {YEAR} (series {SERIES}): {len(match_ids)} matches")

all_rows, metas = [], []
t0 = time.time()
for i, mid in enumerate(match_ids, 1):
    print(f"[{i}/{len(match_ids)}] match {mid} ...", flush=True)
    try:
        rows, meta = scrape_match(mid, verbose=True)
    except Exception as e:
        print(f"  FAILED: {e}", flush=True)
        metas.append({"match_id": mid, "name": "SCRAPE FAILED", "description": str(e),
                      "date": "", "status": "error", "winner": "", "deliveries": 0})
        continue
    all_rows += rows
    metas.append(meta)

meta_fields = ["match_id", "name", "description", "date", "status",
               "home_team", "home_score", "away_team", "away_score",
               "winner", "deliveries"]
with (ROOT / f"tnpl_{YEAR}_matches.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=meta_fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(metas)

with (ROOT / f"tnpl_{YEAR}_bbb.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=all_rows[0].keys())
    w.writeheader()
    w.writerows(all_rows)

print(f"\nDone in {(time.time() - t0) / 60:.1f} min: {len(all_rows)} deliveries "
      f"from {sum(1 for m in metas if m.get('deliveries'))} matches")
print(f"Wrote tnpl_{YEAR}_bbb.csv and tnpl_{YEAR}_matches.csv")
