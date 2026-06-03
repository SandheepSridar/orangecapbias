# MOVI — Middle-Order Value Index (Paper 2 notes)

**Status:** Core contribution for Paper 2 ("a corrected Best Batsman Index"), and a
strong reinforcing exhibit for Paper 1's structural-bias thesis.

MOVI identifies the best **middle-order** batsman (average batting position 4–7,
7+ matches) in each IPL season, scoring them on what the Orange Cap ignores —
rate, finishing and reliability rather than raw run volume.

---

## The index (v1)

Four components, each standardised **within each season** (z-score over the
qualifying middle-order pool), then averaged with **equal weight**:

| Component | Metric |
|---|---|
| Volume | mean runs per innings |
| Efficiency | strike rate (legal balls; wides excluded) |
| Finishing | death-over (16–20) strike rate |
| Consistency | **median** runs per innings (robust to one-off big scores) |

`MOVI = mean(z_volume, z_efficiency, z_finishing, z_consistency)`. The season's
Orange Cap winner is excluded (a no-op: no winner has ever averaged above
position 3). Script: `src/middle_order_index.py`; outputs
`outputs/tables/middle_order_index_best.csv` (one per season) and
`middle_order_index_all.csv` (all qualifying batter-seasons, ranked).

**Recurring names:** AB de Villiers (3×: 2012/14/20), H Klaasen (3×: 2023/25/26),
A Russell & G Maxwell (2× each). Most dominant single season: Russell 2019
(MOVI 2.54, striking 205 from No. 5).

---

## Finding 1 — they out-strike the run-leader

In **17 of 19** seasons the MOVI #1 had a higher season strike rate than that
season's leading run-scorer (the Orange Cap winner), by an average of ~19 runs
per 100 balls. The only two exceptions are themselves explosive openers
(Gayle 2011, Suryavanshi 2026). The middle order's best are faster *and* score
under harder conditions — they simply face fewer balls.

---

## Finding 2 — the league barely recognises them

Cross-referenced every MOVI season-topper against that season's individual player
awards (MVP / Man of the Tournament, Emerging Player, Super Striker, Best Catch),
per Wikipedia's *List of IPL awards*.

**17 of 19 MOVI season-toppers won no individual IPL award that season.** Only
Andre Russell broke through — 2015 (MVP) and 2019 (MVP + Super Striker).

| Season | MOVI #1 | Other individual award that season |
|---|---|---|
| 2008 | RG Sharma | — |
| 2009 | A Symonds | — |
| 2010 | RV Uthappa | — |
| 2011 | MS Dhoni | — |
| 2012 | AB de Villiers | — |
| 2013 | DA Miller | — |
| 2014 | AB de Villiers | — |
| 2015 | AD Russell | **Most Valuable Player** |
| 2016 | KH Pandya | — |
| 2017 | GJ Maxwell | — |
| 2018 | KD Karthik | — |
| 2019 | AD Russell | **MVP + Super Striker** |
| 2020 | AB de Villiers | — |
| 2021 | GJ Maxwell | — |
| 2022 | TH David | — |
| 2023 | H Klaasen | — |
| 2024 | T Stubbs | — |
| 2025 | H Klaasen | — |
| 2026 | H Klaasen | — (provisional) |

**Two sharper points for the write-up:**
1. **Even the exceptions weren't recognised as batsmen.** Russell's MVP is an
   *all-rounder* award (it folds in bowling and fielding). In 19 seasons, the best
   middle-order *batting* season was honoured by a batting-specific award exactly
   once — Russell's 2019 Super Striker. Every other year: nothing.
2. **The talent was obvious, just never in the right season.** Several won awards
   in *other* years — Rohit Sharma (Emerging 2009, but MOVI-top 2008), Karthik
   (Super Striker 2022, MOVI-top 2018), Maxwell (Super Striker 2023 & MVP 2014,
   MOVI-top 2017 & 2021). Recognition existed; it just never landed in the season
   their middle-order batting was actually best.

**Caveats:**
- 2026 award data on Wikipedia is incomplete/early (only MVP + Emerging listed,
  both Suryavanshi); treat 2026 "unrecognised" as provisional.
- Comparison covers MVP, Emerging Player, Super Striker, Best Catch. Niche awards
  (Most Sixes / Game Changer / Power Player) were not fully captured per season —
  spot-check before publishing an absolute "completely unrecognised" claim.
- Source data: `data/reference/movi_recognition.csv` (one row per season).

---

## Where this fits

- **Paper 2:** MOVI is the proposed metric; Finding 2 motivates *why a new award
  is needed* — the recognition gap is quantified, not asserted.
- **Paper 1 (Discussion):** Finding 2 also reinforces the structural-bias argument
  — the middle order's best are not just denied the Orange Cap, they are denied
  *all* individual recognition almost every season. Pairs naturally with the
  Super Striker analysis ([[super_striker_analysis]]).
