"""TNPL mirror of src/middle_order_index.py — MOVI (Middle-Order Value Index).

Same v1 definition as the IPL study: for each season, middle-order batsmen
(avg position 4–7) are scored on an equal-weighted composite of four
within-season z-scored components:

  Volume      = mean runs per innings
  Efficiency  = strike rate (legal balls; wides excluded)
  Finishing   = death-over (16-20) strike rate
  Consistency = median runs per innings

Index = mean(z_volume, z_efficiency, z_finishing, z_consistency).

One threshold is rescaled: qualification is 4+ matches (IPL: 7+ of a 14-match
league; TNPL's league is 7 matches — same ~50% bar).

Also writes movi_recognition.csv: each season's MOVI #1 cross-referenced
against TNPL's individual awards (Player of the series, Most Runs) from
reference_awards.csv.

Usage:  python3 TNPL/middle_order_index.py
"""

import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "tnpl_ball_by_ball.csv"
OUT = ROOT / "tables"
OUT.mkdir(exist_ok=True)

MIN_MATCHES = 4

bbb = pd.read_csv(RAW, keep_default_na=False)
bbb = bbb[bbb["innings"].isin([1, 2])]
bbb = bbb[bbb["batter"] != "UNKNOWN"]
legal = bbb[bbb["extras_type"] != "wide"]            # SR / balls faced exclude wides

# ── batter-season aggregates ────────────────────────────────────────────────
agg = bbb.groupby(["season", "batter"]).agg(
    runs=("runs_batter", "sum"),
    avg_pos=("batting_position", "mean"),
    matches=("match_id", "nunique"),
    team=("batting_team", lambda x: x.mode().iloc[0]),
).reset_index()
balls = legal.groupby(["season", "batter"])["runs_batter"].count().rename("balls").reset_index()
agg = agg.merge(balls, on=["season", "batter"], how="left")
agg["balls"] = agg["balls"].fillna(0).astype(int)

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

agg = agg[agg["balls"] > 0].copy()
agg["sr"] = agg["runs"] / agg["balls"] * 100
agg["death_sr"] = np.where(agg["death_balls"] > 0, agg["death_runs"] / agg["death_balls"] * 100, np.nan)

# ── qualify: middle order (4 <= avg_pos <= 7), 4+ matches ────────────────────
q = agg[(agg["avg_pos"] >= 4) & (agg["avg_pos"] <= 7) & (agg["matches"] >= MIN_MATCHES)].copy()


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

# ── save ────────────────────────────────────────────────────────────────────
cols = ["season", "batter", "team", "avg_pos", "matches", "innings", "runs",
        "mean_rpi", "median_rpi", "sr", "death_sr",
        "z_volume", "z_efficiency", "z_finishing", "z_consistency", "index"]
rounding = {"avg_pos": 2, "mean_rpi": 1, "sr": 1, "death_sr": 1,
            "z_volume": 2, "z_efficiency": 2, "z_finishing": 2, "z_consistency": 2, "index": 2}

best_out = best[cols].round(rounding)
best_out.to_csv(OUT / "middle_order_index_best.csv", index=False)

all_out = q.copy()
all_out["season_rank"] = all_out.groupby("season")["index"].rank(ascending=False, method="min").astype(int)
all_out = all_out[cols + ["season_rank"]].round(rounding).sort_values(["season", "season_rank"])
all_out.to_csv(OUT / "middle_order_index_all.csv", index=False)

# components file (no match floor, position band widened to 3.75 like the IPL one)
comp_cols = ["season", "batter", "team", "avg_pos", "matches", "innings", "runs",
             "mean_rpi", "median_rpi", "sr", "death_sr"]
comp = agg[(agg["avg_pos"] >= 3.75) & (agg["avg_pos"] <= 7)][comp_cols].copy()
comp = comp.round({"avg_pos": 3, "mean_rpi": 4, "median_rpi": 4, "sr": 4, "death_sr": 4})
comp.to_csv(OUT / "middle_order_components.csv", index=False)

# ── recognition: did the MOVI #1 win any TNPL individual award that season? ──
ref = pd.read_csv(ROOT / "reference_awards.csv")


def name_match(a, b):
    """Exact, containment, or shared-surname match across name spellings."""
    a, b = a.strip().lower(), b.strip().lower()
    return a == b or a in b or b in a or a.split()[-1] == b.split()[-1]


rec_rows = []
for _, r in best.iterrows():
    season_ref = ref[ref["season"] == r["season"]]
    awards = []
    if not season_ref.empty:
        row = season_ref.iloc[0]
        if name_match(r["batter"], row["player_of_series"]):
            awards.append("Player of the series")
        if name_match(r["batter"], row["most_runs"]):
            awards.append("Most runs")
    rec_rows.append({"season": int(r["season"]), "batter": r["batter"],
                     "other_award": " + ".join(awards)})
rec = pd.DataFrame(rec_rows)
rec.to_csv(OUT / "movi_recognition.csv", index=False)
unrec = int((rec["other_award"] == "").sum())

print(f"Saved {OUT/'middle_order_index_best.csv'} ({len(best_out)} rows)")
print(f"Saved {OUT/'middle_order_index_all.csv'} ({len(all_out)} rows)")
print(f"Saved {OUT/'middle_order_components.csv'} ({len(comp)} rows)")
print(f"Saved {OUT/'movi_recognition.csv'} — {unrec} of {len(rec)} MOVI #1s "
      f"won no individual TNPL award that season\n")

pd.set_option("display.width", 200, "display.max_columns", None)

print("\nBEST MIDDLE-ORDER BATSMAN PER SEASON (TNPL, v1 index)\n" + "=" * 112)
hdr = (f"{'Season':<7}{'Player':<26}{'Pos':>4}{'Mat':>4}{'Runs':>5}"
       f"{'RPI':>6}{'Med':>5}{'SR':>7}{'DthSR':>7}{'  zVol  zEff  zFin  zCon':>26}{'Index':>8}")
print(hdr)
print("-" * 112)
for _, r in best.iterrows():
    dsr = f"{r['death_sr']:.0f}" if not np.isnan(r["death_sr"]) else "-"
    print(f"{int(r['season']):<7}{r['batter'][:25]:<26}"
          f"{r['avg_pos']:>4.1f}{int(r['matches']):>4}{int(r['runs']):>5}"
          f"{r['mean_rpi']:>6.1f}{r['median_rpi']:>5.0f}{r['sr']:>7.1f}{dsr:>7}"
          f"{r['z_volume']:>6.2f}{r['z_efficiency']:>6.2f}{r['z_finishing']:>6.2f}{r['z_consistency']:>6.2f}"
          f"{r['index']:>8.2f}")

print("\nLegend: Pos=avg batting position, RPI=mean runs/innings, Med=median runs/innings,")
print("        SR=strike rate, DthSR=death-over SR, z*=within-season z-scores, Index=mean of the four z's.")
