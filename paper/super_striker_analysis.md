# Super Striker Award — Supplementary Analysis

**Status:** Supporting analysis for the Discussion section (not a core result).
**Question tested:** *Do middle-order batters win the Super Striker only when their
team's openers fail consistently — or can high-performing top-order and middle-order
batting coexist in the same season?*
**Verdict:** **Disproved.** Middle-order Super Striker winners overwhelmingly come from
teams whose openers were *also* performing well. Top-order and middle-order excellence
are statistical **complements, not substitutes**.

---

## Where this fits in the paper

This belongs in **Section 4 (Discussion)**, in the paragraph on the **Super Striker
award as a partial compensating mechanism** (already foreshadowed in the Introduction's
roadmap).

**Narrative role.** The paper's core claim is that the Orange Cap is structurally biased
against middle-order batsmen because of *volume and opportunity* (balls faced, powerplay
access, match count) — not because middle-order batsmen are less skilled. The Super
Striker award is the natural counterpoint a reviewer would raise: *"but there already is
an award that rewards middle-order strikers."* This analysis strengthens the paper on two
fronts:

1. **The Super Striker does reach the middle order** — 5 of the 9 official winners
   (2018–2026) batted at position 4 or lower — so it partially compensates. But it is an
   SR award with a 100-ball threshold and far less prestige, so it does **not** undo the
   Orange Cap's structural bias.
2. **Middle-order excellence is not contingent on opener failure.** If middle-order
   batsmen only "had their moment" when openers failed, one could argue the Orange Cap
   correctly tracks the genuinely dominant batsmen. The data refutes this: middle-order
   strikers excel *alongside* successful openers. Their omission from the Orange Cap is
   therefore purely structural, reinforcing the paper's central thesis.

**Suggested one-line citation for the Discussion:** "Middle-order Super Striker winners
are not a by-product of opener failure: in 10 of 11 such seasons (and all 5 in the
official-award era) their team's lead opener performed above the league median, and across
all team-seasons opener and middle-order strike rates are positively correlated
(r = +0.32, p < 0.001)."

---

## The hypothesis (formal)

- **H1 (claim):** A middle-order/finisher batter wins the Super Striker *only* when the
  openers on their team fail consistently that season.
- **H0 (null / what we find):** Middle-order Super Striker performances occur independently
  of — or alongside — strong opener performances.

H1 predicts a **negative** relationship between a team's opener output and its
middle-order output. The data shows the opposite.

---

## Data & method

- **Source:** Cricsheet ball-by-ball, 2008–2026 (innings 1–2 only), the same dataset used
  for the main analyses.
- **Strike rate:** `runs / legal_balls × 100`, where legal balls exclude wides (consistent
  with the IPL's official SR calculation — see validation below).
- **Super Striker (data-driven):** the batter with the highest season strike rate among
  those with **≥ 100 legal balls**, one per season. This is the official award's exact
  criterion.
- **Position group:** by season-average batting position — Opener (1–2), Top Order (3),
  Middle Order (4–5), Finisher (6+).
- **"Opener failed":** the team's best opening batter (pos ≤ 2) scored **fewer runs than
  the league-median opener** that season.

---

## Validation against the official record

The data-driven reconstruction reproduces the **official Super Striker winners exactly —
all 9, to the decimal** (Wikipedia, 2018–2026):

| Season | Winner | Team | Official SR | Reconstructed SR |
|---|---|---|---|---|
| 2018 | Sunil Narine | KKR | 189.89 | 189.9 |
| 2019 | Andre Russell | KKR | 204.8 | 204.8 |
| 2020 | Kieron Pollard | MI | 191.42 | 191.4 |
| 2021 | Shimron Hetmyer | DC | 168.05 | 168.1 |
| 2022 | Dinesh Karthik | RCB | 183.33 | 183.3 |
| 2023 | Glenn Maxwell | RCB | 183.48 | 183.5 |
| 2024 | Jake Fraser-McGurk | DC | 234.04 | 234.0 |
| 2025 | Vaibhav Suryavanshi | RR | 206.55 | 206.6 |
| 2026 | Vaibhav Suryavanshi | RR | 237.30 | 237.3 |

This confirms the SR methodology and that the hypothesis test uses the *actual* winners.

---

## Results — three independent lines of evidence

### 1. The middle-order winners themselves
Across 2008–2026 there are **11 middle-order/finisher** data-driven Super Striker winners.
In **10 of 11**, their team's best opener performed **above** the league-median opener that
season. The five official-award-era cases are unanimous:

| Season | SS winner (group) | Team's best opener | Opener runs @ SR | vs league median |
|---|---|---|---|---|
| 2019 | A. Russell (Finisher) | C. Lynn | 405 @ 139.7 | above |
| 2020 | K. Pollard (Finisher) | Q. de Kock | 503 @ 140.5 | above |
| 2021 | S. Hetmyer (Finisher) | S. Dhawan | 587 @ 124.6 | above |
| 2022 | D. Karthik (Finisher) | F. du Plessis | 468 @ 127.5 | above |
| 2023 | G. Maxwell (Middle) | F. du Plessis | 730 @ 153.7 | **well above** |

The single partial exception (2013, D. Miller, Punjab) had a team opener only marginally
below median (Gilchrist, 294 runs @ 128 SR) — not a "consistent failure."

**Standout counterexample:** 2023 RCB — Glenn Maxwell won the Super Striker from the
middle order in the *same* season Faf du Plessis opened with 730 runs at a 153.7 strike
rate, one of the strongest opening seasons on record.

### 2. League-wide co-occurrence
Across **165 team-seasons** that fielded both a qualifying opener and a qualifying
middle-order/finisher (≥ 100 balls each), **103 (62%)** had *both* performing above the
league-median strike rate. Coexistence is the norm, not the exception.

### 3. Correlation (the decisive test)
The hypothesis predicts a negative relationship. Observed:

> **Pearson r = +0.324, p < 0.0001** between a team's best-opener SR and its
> best-middle/finisher SR.

The relationship is **positive** — teams with a high-strike-rate opener tend to *also*
have a high-strike-rate middle-order batter.

---

## The 100-ball eligibility gate excludes the disadvantaged positions

The Super Striker requires a batter to face **≥ 100 legal balls** to qualify. Because
lower-order batters face fewer balls *by virtue of where they bat* — the paper's core
structural claim — this gate falls hardest on exactly the players the award is meant to
reward, and in several seasons it excluded batters who **out-struck the actual winner**.

**Batters who beat their season's Super Striker winner's strike rate but were ineligible
(< 100 balls):**

| Min. balls floor | Count excluded | Position-group split |
|---|---|---|
| ≥ 50 balls | 8 | 6 Finisher, 1 Middle, 1 Opener — **7/8 (88%) lower-order** |
| ≥ 30 balls | 16 | 13 Finisher, 1 Middle, 1 Top Order, 1 Opener — **14/16 (88%) lower-order** |

These are not small-sample flukes — they are 60–94 ball innings at extreme strike rates:

| Season | Player (group) | Runs / Balls | SR | Actual winner (SR) |
|---|---|---|---|---|
| 2023 | Rashid Khan (Finisher, GT) | 130 / 60 | 216.7 | Maxwell (183.5) |
| 2022 | Tim David (Finisher, MI) | 186 / 86 | 216.3 | Karthik (183.3) |
| 2018 | K. Gowtham (Finisher, RR) | 126 / 64 | 196.9 | Narine (189.9) |
| 2014 | J. Faulkner (Finisher, RR) | 181 / 94 | 192.6 | Maxwell (187.8) |

The gate's composition makes the structural skew explicit:

| Pool | Middle-order + Finisher share |
|---|---|
| Below the gate (< 100 balls, ≥ 30) | **81.6%** |
| Above the gate (≥ 100 balls, eligible) | 58.0% |

**Double exclusion.** Lower-order batters face fewer balls because of where they bat, and
then a *balls-faced* eligibility gate removes them from the one award designed to reward
them. Even the supposed compensating mechanism re-imposes the same structural filter.

*Caveat for the paper:* a minimum threshold is defensible for sample reliability — but
expressing it in **innings** rather than **balls** would stop penalising batters purely
for batting lower in the order.

---

## Interpretation

Opener and middle-order strike rates share **common causes** — a flat pitch, a strong
batting unit, a favourable match-up environment lift *every* position simultaneously. They
are complements, not substitutes. A middle-order batter does not need the openers to fail
in order to strike at a high rate; both flourish together.

---

## Caveats / limitations

- "Super Striker (data-driven)" uses max season SR with ≥ 100 balls; validated to match
  the official winners 2018–2026.
- "Team's best opener / middle-order" uses the single highest performer (a max), so
  within-team batting-slot dynamics are not modelled. The directional conclusion is robust
  across all three tests regardless.
- Strike rate excludes wides (IPL convention); no-balls are counted as faced.

---

## Reproducibility

Computed from `data/processed/ball_by_ball.parquet`. Core logic:

```python
import pandas as pd
from scipy import stats

df = pd.read_parquet("data/processed/ball_by_ball.parquet")
df = df[df.innings.isin([1, 2])]
legal = df[df.extras_type != "wide"]            # SR excludes wides

bs = (legal.groupby(["season", "batter"])
      .agg(balls=("runs_batter", "count"), runs=("runs_batter", "sum"),
           avg_pos=("batting_position", "mean"),
           team=("batting_team", lambda x: x.mode().iloc[0]))
      .reset_index())
bs["sr"] = bs.runs / bs.balls * 100
q = bs[bs.balls >= 100]                          # Super Striker threshold

# Data-driven Super Striker per season = max SR
ss = q.loc[q.groupby("season").sr.idxmax()]

# Team-season co-occurrence + correlation
op = q[q.avg_pos <= 2].groupby(["season", "team"]).sr.max().rename("op_sr")
mf = q[q.avg_pos > 3].groupby(["season", "team"]).sr.max().rename("mf_sr")
ts = pd.concat([op, mf], axis=1).dropna()
r, p = stats.pearsonr(ts.op_sr, ts.mf_sr)        # r = +0.324, p < 0.0001

# 100-ball gate: high-SR batters excluded for facing < 100 balls
win_sr = ss.set_index("season").sr
cand = bs[(bs.balls >= 50) & (bs.balls < 100)].copy()
cand["win_sr"] = cand.season.map(win_sr)
excluded = cand[cand.sr > cand.win_sr]            # beat the winner's SR but ineligible
```
