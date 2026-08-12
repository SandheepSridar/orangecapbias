"""Combine raw_scorecards/<prefix>_batch_*.csv files into final split batting/bowling CSVs."""
import sys
import glob
import os

def combine(prefix, out_dir):
    files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "data", "raw_scorecards", f"{prefix}_batch_*.csv")))
    batting_rows = []
    bowling_rows = []
    match_ids = set()
    for f in files:
        with open(f, encoding="utf-8") as fh:
            content = fh.read()
        parts = content.split("===BOWLING===")
        bat_part = parts[0].strip("\n")
        bowl_part = parts[1].strip("\n") if len(parts) > 1 else ""
        for line in bat_part.split("\n"):
            if line.strip():
                batting_rows.append(line)
                match_ids.add(line.split(",")[0])
        for line in bowl_part.split("\n"):
            if line.strip():
                bowling_rows.append(line)
                match_ids.add(line.split(",")[0])

    bat_header = "matchId,team,player,dismissal,R,B,4s,6s,SR"
    bowl_header = "matchId,team,bowler,O,M,Dot,R,W,Econ,wides,noballs"

    bat_out = os.path.join(out_dir, f"{prefix}_scorecards_batting.csv")
    bowl_out = os.path.join(out_dir, f"{prefix}_scorecards_bowling.csv")
    with open(bat_out, "w", encoding="utf-8") as fh:
        fh.write(bat_header + "\n")
        fh.write("\n".join(batting_rows) + "\n")
    with open(bowl_out, "w", encoding="utf-8") as fh:
        fh.write(bowl_header + "\n")
        fh.write("\n".join(bowling_rows) + "\n")

    print(f"{prefix}: {len(files)} batch files, {len(match_ids)} unique matchIds, "
          f"{len(batting_rows)} batting rows, {len(bowling_rows)} bowling rows")
    return match_ids

if __name__ == "__main__":
    prefix = sys.argv[1]
    out_dir = os.path.join(os.path.dirname(__file__), "data")
    combine(prefix, out_dir)
