"""Merge raw_scorecards/<prefix>_new_*.csv into the existing data/<series>_scorecards_*.csv.

Incremental counterpart to combine_scorecards.py: any matchId in the new batches replaces
that match's existing rows (so a re-fetched correction overwrites cleanly); every other line
in the combined CSVs is kept byte-for-byte.

Usage: python3 merge_new_scorecards.py d1 division1
       python3 merge_new_scorecards.py wk weekenderscup
"""
import sys
import glob
import os

HERE = os.path.dirname(__file__)


def read_batches(prefix):
    files = sorted(glob.glob(os.path.join(HERE, "data", "raw_scorecards", f"{prefix}_new_*.csv")))
    batting, bowling = [], []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            parts = fh.read().split("===BOWLING===")
        batting += [l for l in parts[0].split("\n") if l.strip()]
        if len(parts) > 1:
            bowling += [l for l in parts[1].split("\n") if l.strip()]
    return files, batting, bowling


def merge(path, new_rows, new_ids):
    with open(path, encoding="utf-8") as fh:
        lines = [l for l in fh.read().split("\n") if l.strip()]
    header, body = lines[0], lines[1:]
    kept = [l for l in body if l.split(",")[0] not in new_ids]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join([header] + kept + new_rows) + "\n")
    return len(body) - len(kept)


if __name__ == "__main__":
    prefix, series = sys.argv[1], sys.argv[2]
    files, batting, bowling = read_batches(prefix)
    new_ids = {l.split(",")[0] for l in batting + bowling}
    replaced_bat = merge(os.path.join(HERE, "data", f"{series}_scorecards_batting.csv"), batting, new_ids)
    replaced_bowl = merge(os.path.join(HERE, "data", f"{series}_scorecards_bowling.csv"), bowling, new_ids)
    print(f"{prefix}: {len(files)} batch files, {len(new_ids)} matchIds {sorted(new_ids)}, "
          f"+{len(batting)} batting / +{len(bowling)} bowling rows "
          f"(replaced {replaced_bat} / {replaced_bowl} existing)")
