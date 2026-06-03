"""
Best Middle-Order Index (v1) — Paper 2 exploration.

For each season, ranks middle-order batsmen (avg position > 3 and <= 7, 7+ matches)
by an equal-weighted composite of four within-season z-scored components:

  Volume      = mean runs per innings
  Efficiency  = strike rate (legal balls; wides excluded)
  Finishing   = death-over (16-20) strike rate
  Consistency = median runs per innings (robust to one-off big scores)

Index = mean(z_volume, z_efficiency, z_finishing, z_consistency).
The season's Orange Cap winner is excluded (a no-op in practice: no winner has
ever averaged above position 3, so none fall in the 4-7 band).

Usage:  python3 src/middle_order_index.py
"""

import numpy as np
import pandas as pd
from pathlib import Path

RAW = Path("data/processed/ball_by_ball.parquet")

bbb = pd.read_parquet(RAW)
bbb = bbb[bbb["innings"].isin([1, 2])]
legal = bbb[bbb["extras_type"] != "wide"]            # SR / balls faced exclude wides

# ── batter-season aggregates ────────────────────────────────────────────────
agg = bbb.groupby(["season", "batter"]).agg(
    runs=("runs_batter", "sum"),
    avg_pos=("batting_position", "mean"),
    matches=("match_id", "nunique"),
    team=("batting_team", lambda x: x.mode().iloc[0]),
).reset_index()
agg["balls"] = legal.groupby(["season", "batter"])["runs_batter"].count().values

# per-innings scores -> mean (volume) and median (consistency)
inns = bbb.groupby(["season", "batter", "match_id"])["runs_batter"].sum().reset_index()
inns_stats = inns.groupby(["season", "batter"])["runs_batter"].agg(
    mean_rpi="mean", median_rpi="median", innings="count").reset_index()
agg = agg.merge(inns_stats, on=["season", "batter"])

# death-over (16-20) strike rate
death = legal[legal["phase"] == "death"]
death_stats = death.groupby(["season", "batter"]).agg(
    death_runs=("runs_batter", "sum"), death_balls=("runs_batter", "count")).reset_index()
agg = agg.merge(death_stats, on=["season", "batter"], how="left")
agg["death_balls"] = agg["death_balls"].fillna(0)
agg["death_runs"] = agg["death_runs"].fillna(0)

agg["sr"] = agg["runs"] / agg["balls"] * 100
agg["death_sr"] = np.where(agg["death_balls"] > 0, agg["death_runs"] / agg["death_balls"] * 100, np.nan)

# ── qualify: middle order (4 <= avg_pos <= 7), 7+ matches ────────────────────
q = agg[(agg["avg_pos"] >= 4) & (agg["avg_pos"] <= 7) & (agg["matches"] >= 7)].copy()


def zscore(s):
    sd = s.std(ddof=1)
    return (s - s.mean()) / sd if sd and not np.isnan(sd) else s * 0.0


# players with no death balls get the season-mean death_sr -> neutral (z = 0)
q["death_sr_f"] = q.groupby("season")["death_sr"].transform(lambda s: s.fillna(s.mean()))

q["z_volume"]      = q.groupby("season")["mean_rpi"].transform(zscore)
q["z_efficiency"]  = q.groupby("season")["sr"].transform(zscore)
q["z_finishing"]   = q.groupby("season")["death_sr_f"].transform(zscore)
q["z_consistency"] = q.groupby("season")["median_rpi"].transform(zscore)

q["index"] = q[["z_volume", "z_efficiency", "z_finishing", "z_consistency"]].mean(axis=1)

# ── best per season ─────────────────────────────────────────────────────────
best = q.loc[q.groupby("season")["index"].idxmax()].sort_values("season")

# ── save for the paper ──────────────────────────────────────────────────────
OUT = Path("outputs/tables")
OUT.mkdir(parents=True, exist_ok=True)
cols = ["season", "batter", "team", "avg_pos", "matches", "innings", "runs",
        "mean_rpi", "median_rpi", "sr", "death_sr",
        "z_volume", "z_efficiency", "z_finishing", "z_consistency", "index"]
rounding = {"avg_pos": 2, "mean_rpi": 1, "sr": 1, "death_sr": 1,
            "z_volume": 2, "z_efficiency": 2, "z_finishing": 2, "z_consistency": 2, "index": 2}

best_out = best[cols].round(rounding)
best_out.to_csv(OUT / "middle_order_index_best.csv", index=False)

# full ranking of every qualifying middle-order batter-season (rank within season)
all_out = q.copy()
all_out["season_rank"] = all_out.groupby("season")["index"].rank(ascending=False, method="min").astype(int)
all_out = all_out[cols + ["season_rank"]].round(rounding).sort_values(["season", "season_rank"])
all_out.to_csv(OUT / "middle_order_index_all.csv", index=False)
print(f"Saved {OUT/'middle_order_index_best.csv'} ({len(best_out)} rows)")
print(f"Saved {OUT/'middle_order_index_all.csv'} ({len(all_out)} rows)\n")

pd.set_option("display.width", 200, "display.max_columns", None)

print("\nBEST MIDDLE-ORDER BATSMAN PER SEASON (v1 index)\n" + "=" * 110)
hdr = (f"{'Season':<7}{'Player':<18}{'Team':<6}{'Pos':>4}{'Mat':>4}{'Runs':>5}"
       f"{'RPI':>6}{'Med':>5}{'SR':>7}{'DthSR':>7}{'  zVol  zEff  zFin  zCon':>26}{'Index':>8}")
print(hdr)
print("-" * 110)
team_abbr = {  # compact display only
    "Mumbai Indians": "MI", "Chennai Super Kings": "CSK", "Royal Challengers Bangalore": "RCB",
    "Royal Challengers Bengaluru": "RCB", "Kolkata Knight Riders": "KKR", "Rajasthan Royals": "RR",
    "Sunrisers Hyderabad": "SRH", "Delhi Capitals": "DC", "Delhi Daredevils": "DD",
    "Kings XI Punjab": "KXIP", "Punjab Kings": "PBKS", "Deccan Chargers": "DEC",
    "Gujarat Titans": "GT", "Lucknow Super Giants": "LSG", "Gujarat Lions": "GL",
    "Rising Pune Supergiant": "RPS", "Rising Pune Supergiants": "RPS", "Pune Warriors": "PW",
    "Kochi Tuskers Kerala": "KTK",
}
for _, r in best.iterrows():
    dsr = f"{r['death_sr']:.0f}" if not np.isnan(r["death_sr"]) else "-"
    print(f"{int(r['season']):<7}{r['batter'][:17]:<18}{team_abbr.get(r['team'], r['team'][:5]):<6}"
          f"{r['avg_pos']:>4.1f}{int(r['matches']):>4}{int(r['runs']):>5}"
          f"{r['mean_rpi']:>6.1f}{r['median_rpi']:>5.0f}{r['sr']:>7.1f}{dsr:>7}"
          f"{r['z_volume']:>6.2f}{r['z_efficiency']:>6.2f}{r['z_finishing']:>6.2f}{r['z_consistency']:>6.2f}"
          f"{r['index']:>8.2f}")

print("\nLegend: Pos=avg batting position, RPI=mean runs/innings, Med=median runs/innings,")
print("        SR=strike rate, DthSR=death-over SR, z*=within-season z-scores, Index=mean of the four z's.")
