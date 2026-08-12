"""Build website/data.js from the project CSVs.

Embeds (1) raw middle-order components so the site can recompute MOVI live at
any threshold, (2) each season's leading run-scorer (the de-facto Orange Cap
winner) with their strike rate, and (3) the award-recognition lookup.
Run from the repo root: python website/build_data.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "data.js"

comp = pd.read_csv(ROOT / "outputs/tables/middle_order_components.csv")
bs = pd.read_csv(ROOT / "outputs/tables/batter_season.csv")
rec = pd.read_csv(ROOT / "data/reference/movi_recognition.csv")

comp_cols = ["season", "batter", "team", "avg_pos", "matches", "innings",
             "runs", "mean_rpi", "median_rpi", "sr", "death_sr"]
comp_rows = []
for r in comp[comp_cols].itertuples(index=False):
    row = list(r)
    row[3] = round(row[3], 2)   # avg_pos
    row[7] = round(row[7], 1)   # mean_rpi
    row[8] = round(row[8], 1)   # median_rpi
    row[9] = round(row[9], 1)   # sr
    row[10] = None if pd.isna(row[10]) else round(row[10], 1)  # death_sr
    comp_rows.append(row)

oc = bs.loc[bs.groupby("season")["runs"].idxmax()].sort_values("season")
oc_rows = [[int(r.season), r.batter, int(r.runs),
            round(r.runs / r.balls_faced * 100, 1)]
           for r in oc.itertuples(index=False)]

rec_rows = [[int(r.season), r.batter, r.other_award] for r in rec.itertuples(index=False)]

payload = (
    "const MOVI_DATA = {\n"
    f"  compCols: {json.dumps(comp_cols)},\n"
    f"  comp: {json.dumps(comp_rows)},\n"
    "  // [season, batter, runs, strike rate] of the season's leading run-scorer\n"
    f"  ocWinners: {json.dumps(oc_rows)},\n"
    f"  recognition: {json.dumps(rec_rows)}\n"
    "};\n"
)
OUT.write_text(payload)
print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB, {len(comp_rows)} component rows)")
