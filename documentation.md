# Script Documentation — IPL Orange Cap Bias Research

This file documents every SQL and Python script in the repository: what it does, what it reads, and what it produces. Run `/update-docs` to regenerate after adding or changing scripts.

---

## Python Scripts

### `src/parse_cricsheet.py`

**Purpose:** Parses all Cricsheet IPL match JSON files into a single flat ball-by-ball DataFrame and saves it as a Parquet file.

**Reads:**
- `data/raw/ipl_json/*.json` — one JSON per match, downloaded from cricsheet.org

**Writes:**
- `data/processed/ball_by_ball.parquet` — 295,732 rows × 21 columns (all seasons 2007/08–2026)

**Key logic:**
- `_season_year()` — extracts 4-digit year from match date (handles split labels like "2007/08")
- `_match_stage()` — normalises event stage strings to clean labels: `league`, `qualifier_1`, `qualifier_2`, `eliminator`, `semi_final`, `third_place`, `final`
- `_phase()` — assigns powerplay / middle / death based on 0-indexed over number
- `parse_match()` — parses one JSON file; derives `batting_position` (order of arrival at the crease per innings, from both `batter` and `non_striker`) and `extras_type` (wide / noball / bye / legbye / penalty / None)
- `parse_all()` — iterates all JSONs, concatenates rows, tightens dtypes, saves parquet

**Output schema:**

| Column | Type | Notes |
|---|---|---|
| match_id | str | Cricsheet filename stem |
| season | int16 | 4-digit year |
| date | str | Match date (YYYY-MM-DD) |
| match_stage | category | league / qualifier_1 / qualifier_2 / eliminator / final |
| batting_team | str | |
| bowling_team | str | |
| innings | int8 | 1 or 2 (super overs excluded downstream) |
| over | int8 | 1-based |
| ball | int8 | Delivery index within over, 1-based (>6 = extra delivery) |
| batter | str | Cricsheet player name |
| bowler | str | |
| runs_batter | int8 | Runs scored by batter off this delivery |
| runs_extras | int8 | Extras runs (wides, no-balls, byes, leg-byes) |
| runs_total | int8 | Total runs for the delivery |
| is_wicket | bool | |
| wicket_kind | str | caught / bowled / run out / etc., or None |
| batting_position | int8 | Order of arrival at the crease in this innings (striker + non_striker) |
| phase | category | powerplay / middle / death |
| extras_type | category | wide / noball / bye / legbye / penalty / None |
| is_dls | bool | True if match affected by D/L method |
| winner | str | Winning team name |

**To re-run:** `python src/parse_cricsheet.py`

---

### `src/build_tables.py`

**Purpose:** Regenerates the per-batter aggregate and five of the six analysis tables directly from the local parquet — the Python equivalent of `analysis_queries.sql`, so the full pipeline can run without Databricks. Validated to reproduce the committed 2008–2025 numbers exactly before being extended to 2026.

**Reads:**
- `data/processed/ball_by_ball.parquet`
- `data/reference/orange_cap_winners.csv` (for Analysis A)

**Writes (to `outputs/tables/`):**
- `batter_season.csv` — qualifying (7+ match) batter-seasons; consumed by `app.py` and `visualize.py`
- `analysis_a_winner_positions.csv`
- `analysis_b_balls_faced_by_position.csv`
- `analysis_c_powerplay_concentration.csv`
- `analysis_e_playoff_match_advantage.csv`
- `analysis_f_non_playoff_elite.csv`

`analysis_d_normalised_rankings.csv` and `stats_results.csv` are **not** produced here — they come from `stats.py`.

**Key decisions:**
- `balls_faced` counts legal deliveries only (wides excluded; no-balls are faced) — same convention as `stats.py`
- `round1()` helper rounds half-up to match SQL `ROUND`, not numpy's banker's rounding — required to reproduce the SQL-generated CSVs to the decimal
- Analyses B and F apply the 7+ match minimum; Analyses C and E run over all batter-seasons (matching the SQL methodology, where C/E have no minimum)
- `MAX_SEASON` (first CLI argument, default 2026) caps the season filter

**To re-run:** `python src/build_tables.py [MAX_SEASON]` (default 2026)

---

### `src/stats.py`

**Purpose:** Runs all 6 statistical hypothesis tests supporting the Orange Cap bias claims. Regenerates two output CSVs.

**Reads:**
- `data/processed/ball_by_ball.parquet`
- `data/reference/orange_cap_winners.csv`

**Writes:**
- `outputs/tables/stats_results.csv` — one row per test with statistic, p-value, significance flag, notes
- `outputs/tables/analysis_d_normalised_rankings.csv` — top-10 batters per season with actual and normalised ranks plus 95% CI columns

**Key decisions:**
- Filters to `season <= 2026` and `innings IN (1, 2)` (all 19 complete seasons; super overs are innings 3+ and excluded)
- Uses `bbb_legal = bbb[bbb["extras_type"] != "wide"]` for all balls-faced calculations — wides are not faced by the batter and are excluded for consistency with official IPL strike rate calculations
- Minimum 7 matches to qualify for population comparisons (avoids single-appearance noise)

**Tests run:**

| Test | Analysis | Method | Question |
|---|---|---|---|
| A | Winner positions | Chi-square | Do winner positions differ from population distribution? |
| B | Balls faced | Kruskal-Wallis + Mann-Whitney U | Do position groups face different numbers of balls? |
| C | Powerplay % | Kruskal-Wallis | Does powerplay run share differ across position groups? |
| D | Normalised rankings | Wilcoxon signed-rank | Do actual and normalised ranks differ significantly? |
| E | Match count | Mann-Whitney U | Do playoff teams play more matches? |
| F | Non-playoff runs | Mann-Whitney U | Do playoff top-5 batters score more than non-playoff top-5? |

**To re-run:** `python src/stats.py`

---

### `src/visualize.py`

**Purpose:** Generates all 6 publication-quality figures for the paper. Saves PNG (300 DPI) and SVG for each.

**Reads (all from `outputs/tables/`):**
- `analysis_a_winner_positions.csv` → Figure 1
- `analysis_b_balls_faced_by_position.csv` → Figure 2 (summary table)
- `analysis_c_powerplay_concentration.csv` → Figure 3
- `analysis_d_normalised_rankings.csv` → Figure 5
- `analysis_e_playoff_match_advantage.csv` → Figure 6
- `batter_season.csv` → Figures 2 (box plot) and 4 (scatter)
- `data/reference/orange_cap_winners.csv` → Figure 6 annotation

**Writes (to `outputs/figures/`):**

| File | Chart type | Key message |
|---|---|---|
| `fig1_winner_positions.png/.svg` | Bar chart | 17/19 winners are openers; zero middle-order ever |
| `fig2_balls_faced.png/.svg` | Box plot | Openers face 71 more balls/season than middle order |
| `fig3_powerplay_concentration.png/.svg` | Stacked bar | Openers score 57.1% of runs in powerplay; middle order 17.3% |
| `fig4_runs_vs_position.png/.svg` | Scatter + trendline | r = −0.61, p < 0.001 negative correlation |
| `fig5_normalised_rankings.png/.svg` | Dot plot | 77.7% of top-10 rankings shift after normalisation |
| `fig6_match_count.png/.svg` | Box plot | Playoff teams play median 2 more matches (~80 free runs) |

**Style:** matplotlib, clean academic style, no dark backgrounds, 300 DPI.

**To re-run:** `python src/visualize.py`

---

### `app.py`

**Purpose:** Streamlit web app that presents all 6 analyses as interactive charts. Designed for public sharing via Streamlit Community Cloud.

**Reads (all from `outputs/tables/` and `data/reference/`):**
- All 6 `analysis_*.csv` files
- `batter_season.csv` (for box plot and scatter raw data)
- `data/reference/orange_cap_winners.csv`

**Does NOT read the parquet** — all data is pre-computed as CSVs so the app deploys on Streamlit Cloud without needing the gitignored parquet file.

**Navigation:** Sidebar radio button (`st.sidebar.radio`) — one section per analysis. Uses sidebar instead of `st.tabs()` to preserve selection state when widgets inside a section trigger reruns.

**Charts (using Plotly):**

| Section | Chart | Interactive feature |
|---|---|---|
| A · Winner Positions | Bar chart | Hover shows season-by-season table |
| B · Balls Faced | Box plot | Hover shows group statistics |
| C · Powerplay Access | Stacked bar | Hover shows phase % per group |
| D · Normalised Rankings | Slope chart + CI lollipop | Season selector; CI chart for batters with <14 matches |
| E · Playoff Advantage | Strip plot | Hover shows team and season |
| F · Non-Playoff Elites | Stacked bar | Hover shows actual vs projected vs OC winner runs |

**To run locally:** `streamlit run app.py`

---

## SQL Scripts

### `src/analysis_queries.sql`

**Purpose:** Six Databricks SQL queries that populate the `outputs/tables/analysis_*.csv` files. Run against `ipl_research.bbb_clean` on Databricks.

**Reads:** `ipl_research.bbb_clean` — a view over `ipl_research.ball_by_ball` filtered to `season <= 2026` and `innings IN (1, 2)`

**Note:** Analysis B in this file does not apply the 7+ match minimum filter. The authoritative Analysis B numbers come from `src/stats.py` (which does apply the filter) and are stored in `outputs/tables/analysis_b_balls_faced_by_position.csv`.

---

**Setup block** — creates the `bbb_clean` view:
```sql
CREATE OR REPLACE VIEW ipl_research.bbb_clean AS
SELECT * FROM ipl_research.ball_by_ball
WHERE season <= 2026 AND innings IN (1, 2);
```

---

**Analysis A — Orange Cap Winner Batting Position**
- Reads from: `ipl_research.orange_cap_winners` (manually seeded reference table)
- Assigns position group from `avg_batting_position`
- Output: 19 rows, one per season
- Writes: `outputs/tables/analysis_a_winner_positions.csv`

---

**Analysis B — Balls Faced by Position Group**
- Aggregates balls faced per batter-season, groups by position group
- ⚠️ Missing 7+ match filter — use stats.py output as authoritative source
- Output: 4 rows (one per position group) with avg/median/min/max balls
- Writes: `outputs/tables/analysis_b_balls_faced_by_position.csv`

---

**Analysis C — Powerplay Run Concentration**
- Pivots phase (powerplay / middle / death) into columns
- Computes percentage of each group's total runs scored per phase
- Output: 4 rows (one per position group)
- Writes: `outputs/tables/analysis_c_powerplay_concentration.csv`

---

**Analysis D — Normalised Rankings**
- League-stage only (`match_stage = 'league'`)
- Normalises runs to 14-match baseline: `norm_runs = league_runs × 14 / league_matches`
- Ranks both actual and normalised; returns top-10 actual or top-10 normalised per season
- Output: ~193 rows (top-10 per season across 19 seasons)
- Writes: `outputs/tables/analysis_d_normalised_rankings.csv`
- ⚠️ The local `stats.py` version also adds 95% CI columns (`ci_lower`, `ci_upper`) — the SQL version does not

---

**Analysis E — Playoff Match Advantage**
- Counts matches played per team per season; flags whether they made playoffs
- Two queries: raw per-team data + summary averages by playoff status
- Output: 166 rows (one per team-season)
- Writes: `outputs/tables/analysis_e_playoff_match_advantage.csv`

---

**Analysis F — Non-Playoff Elite Batsmen**
- Finds batters who ranked top-5 in their season but were on non-playoff teams
- Computes `proj_runs_16_matches = runs × 16 / matches` as the counterfactual
- 7+ match minimum applied via `HAVING`
- Output: 23 rows across 19 seasons
- Writes: `outputs/tables/analysis_f_non_playoff_elite.csv`

---

## Data Files

| File | Description |
|---|---|
| `data/raw/ipl_json/` | Raw Cricsheet JSONs — gitignored, ~350MB |
| `data/processed/ball_by_ball.parquet` | Parsed ball-by-ball data — gitignored, ~4MB |
| `data/reference/orange_cap_winners.csv` | Manually curated Orange Cap winners 2008–2026 |
| `outputs/tables/batter_season.csv` | Per-batter per-season aggregates (legal balls, 7+ matches) — generated by build_tables.py; used by app and visualize.py |
| `outputs/tables/stats_results.csv` | All 6 statistical test results |
| `outputs/figures/` | Publication-quality PNG + SVG figures |
