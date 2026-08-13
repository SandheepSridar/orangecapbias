# TNPL replication of the IPL Orange Cap bias study (2016–2025)

The full IPL pipeline (analyses A–F, the statistical battery, and MOVI) was
re-run on Tamil Nadu Premier League ball-by-ball data: 9 seasons, 285 matches
with play, 66,534 deliveries (ESPN core API; all innings runs reconcile with
official scores; every season's run leader matches the league's Most Runs
award — see `data_quality_report_all.md`).

TNPL's equivalent of the Orange Cap is the **Most Runs award**. Thresholds are
rescaled for the short season (league = 7 matches vs the IPL's 14):
qualification 4+ matches, rank normalisation to the season's league length,
Analysis F projection to 9 matches (= league + 2).

## Headline: the structural bias replicates

Every statistical test from the IPL study is significant in TNPL too:

| Test | Result | IPL equivalent |
|---|---|---|
| A. Winner positions vs population (chi-square) | χ² = 18.4, p < 0.001 | same direction |
| B. Balls faced by position (Kruskal-Wallis) | H = 368.4, p < 0.001 | same |
| B post-hoc Opener > Middle (Mann-Whitney) | median +48 balls/season, p < 0.001 | same |
| C. Powerplay run % by position (Kruskal-Wallis) | H = 728.2, p < 0.001 | same |
| D. Actual vs normalised rank (Wilcoxon) | 42.9% of top-10 ranks shift, p = 0.037 | same |
| E. Matches: playoff vs non-playoff (Mann-Whitney) | median 9 vs 7, p < 0.001 | same |
| F. Runs: playoff vs non-playoff top-5 (Mann-Whitney) | median 336 vs 283, p = 0.041 | same |

Key magnitudes:
- **7 of 9 Most Runs winners were openers** (median avg position 1.7); none was
  a finisher. All 9 played for playoff teams.
- Openers face a **median 144 balls/season vs 96 for middle order** (+50%) and
  score **59% of their runs in the powerplay vs 18%** for the middle order.
- In **3 of 9 seasons (2016, 2019, 2022) the actual run leader loses the top
  spot** once runs are normalised to a full league season. The starkest case:
  **Murali Vijay 2019** — 359 runs in only 4 league matches (~90/match) for
  non-playoff Trichy, ranked 2nd while the winner batted 10 matches.
- The non-playoff elite (Analysis F) includes **Sai Sudharsan, 2023: 371 runs,
  ranked #2 despite his team missing the playoffs** — the same batter who won
  the actual IPL Orange Cap in 2025 — and Baba Aparajith three times.

## One honest difference from the IPL

The IPL has *never* had a Most Runs/Orange Cap winner averaging below position
3 in 19 seasons. TNPL has **two middle-order winners**: Sanjay Yadav 2022
(avg pos 4.2) and Guruswamy Ajitesh 2023 (3.5). The bias is strong but not
absolute in a shorter league — worth stating plainly in any write-up rather
than overclaiming.

## MOVI on TNPL

Same v1 definition (4 components z-scored within season, equal weights,
positions 4–7), 4+ matches to qualify. Outputs in `tables/middle_order_*.csv`.

- **Best middle-order batsman per season:** M Mohammed (2016), Rajendran Vivek
  (2017), Rajagopal Sathish (2018, 2019), Shahrukh Khan (2021, 2024, 2025),
  Sanjay Yadav (2022), Sunny Sandhu (2023).
- **Shahrukh Khan is TNPL's AB de Villiers** — 3 MOVI titles. His 2024 season
  (z-consistency +3.30, death SR 251) is the index's best non-Yadav season.
- **Strike rate:** the MOVI #1 out-struck the season's run leader in **7 of 9
  seasons**, by an average of **+27 runs per 100 balls** (fig7) — larger than
  the IPL's +19.
- **Recognition:** **7 of 9 MOVI #1s won no individual TNPL award** that
  season. The two exceptions are instructive: Sanjay Yadav 2022 won Player of
  the Series + Most Runs *because* he scored opener-volume runs from No. 4 —
  the one season a middle-order batsman out-accumulated everyone — and
  Shahrukh Khan's 2024 Player of the Series. (TNPL awards checked: Player of
  the Series, Most Runs; the league has no batting-specific award beyond Most
  Runs.)
- 2022 is also the season where the run leader and MOVI #1 are the same player
  — the near-overlapping dots in fig7.

## Caveats

- ESPN's pre-2019 data has gaps: ~3–5% of deliveries in 2016–2018 have an
  unknown striker id (excluded from batter-level aggregates; innings totals
  still reconcile). Batting positions there are derived from striker
  appearances plus known non-strikers.
- ESPN rosters apply *current* franchise names retroactively (e.g. Tuti
  Patriots 2016–18 appears as "SKM Salem Spartans"). Within-season team
  identity is consistent, so playoff flags and team aggregates are unaffected.
- Wikipedia's TNPL summary lists Sonu Yadav as 2025 Most Runs; ball-by-ball
  and espncricinfo's tournament report both confirm Tushar Raheja (488). The
  reference CSV uses Raheja.
- 2020 season cancelled (COVID); 2 matches in 2017 fully washed out.

## Reproduce

```bash
python3 TNPL/prepare_data.py                                  # combine + derive fields
uv run --with pandas,scipy,matplotlib python TNPL/build_tables.py
uv run --with pandas,scipy,matplotlib python TNPL/stats.py
uv run --with pandas,scipy,matplotlib python TNPL/middle_order_index.py
uv run --with pandas,scipy,matplotlib python TNPL/visualize.py   # fig1–fig7
python3 TNPL/data_quality_all.py                              # validation report
```
