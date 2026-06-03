# CLAUDE.md — IPL Orange Cap Bias Research Project

This file is the project bible for Claude Code. It contains behavioral guidelines,
full project context, goals, methodology, and task instructions.

---

## Behavioral Guidelines

Reduce common LLM coding mistakes. **Bias toward caution over speed. For trivial tasks, use judgment.**

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## Project Overview

**Title:** *"An Award You Cannot Win from Number Five: Structural Bias in the IPL
Orange Cap"*

**Author Background:** Data Engineer with cricket domain knowledge

**Core Argument:** The IPL Orange Cap award — given to the highest run-scorer each
season — is structurally unfair because it systematically advantages:
1. **Openers and top-order batsmen** (positions 1–3) who face more balls and benefit
   from powerplay fielding restrictions
2. **Players on playoff-qualifying teams** who play 2–3 additional matches

Middle-order batsmen (positions 4–5) and finishers (positions 6+) are disadvantaged
by fewer balls faced, no powerplay access, and reduced match count if their team
misses the playoffs.

**End Goal:** A two-paper research series:
- **Paper 1 (current focus):** Prove the bias statistically using IPL data (2008–2026)
- **Paper 2 (future):** Propose a new "Best Batsman Index" that corrects for these biases

---

## Paper 1 — Scope & Hypothesis

### Research Hypothesis
> *"The IPL Orange Cap award structurally disadvantages middle-order batsmen due to
> (a) fewer balls faced per season, (b) no access to powerplay conditions, and (c)
> reduced match opportunities for players on non-playoff teams."*

### What This Paper Must Prove (Key Claims)
1. The overwhelming majority of Orange Cap winners batted in positions 1–3
2. Openers face significantly more balls per season than middle-order batsmen
3. A disproportionate share of runs scored by openers comes in the powerplay
   (overs 1–6), which middle-order batsmen cannot access
4. Non-playoff teams play ~2–3 fewer matches, creating a structural run-accumulation
   disadvantage even for elite middle-order batsmen
5. If normalized for balls faced (or matches played), several non-winners would
   outrank actual Orange Cap winners in efficiency metrics

### What This Paper Does NOT Do
- It does not propose a replacement scoring system (that is Paper 2)
- It does not use machine learning or complex models
- It does not evaluate bowling performance

---

## Data Source

**Primary:** Cricsheet IPL ball-by-ball data
**Download URL:** `https://cricsheet.org/downloads/ipl_json.zip`
**Coverage:** All 1,241 IPL matches (2008–2026), ball-by-ball JSON format
**Format:** One JSON file per match

### Key Fields Available in Cricsheet JSON
- Ball-by-ball: `batter`, `bowler`, `runs.batter`, `runs.extras`, `wickets`
- Over number → derive phase (powerplay / middle / death)
- Innings metadata: batting team, bowling team
- Match metadata: `season`, `dates`, `event.name`, `match_type`, `outcome`
- Player registry with unique identifiers

### Fields to Derive
| Derived Field | How to Derive |
|---|---|
| `batting_position` | Order of arrival at the crease per innings (striker + non_striker) |
| `position_group` | 1–2=Opener, 3=Top Order, 4–5=Middle Order, 6+=Finisher |
| `phase` | Over 1–6=Powerplay, 7–15=Middle, 16–20=Death |
| `match_stage` | League stage vs Qualifier/Eliminator/Final |
| `playoff_team` | Whether team appeared in playoffs that season |
| `season_runs` | Aggregate runs per batter per season |

---

## Project Structure

```
ipl-orange-cap-bias/
│
├── CLAUDE.md                   ← This file
├── README.md                   ← Public-facing project description
│
├── data/
│   ├── raw/                    ← Downloaded Cricsheet JSON files (gitignored)
│   │   └── ipl_json/           ← Extracted match JSONs
│   ├── processed/              ← Cleaned, flattened dataframes
│   │   ├── ball_by_ball.parquet
│   │   ├── batter_season.parquet
│   │   └── orange_cap_winners.csv
│   └── reference/
│       └── orange_cap_winners.csv   ← Manual list: season, winner, runs, position
│
├── notebooks/
│   ├── 01_data_ingestion.ipynb      ← Parse Cricsheet JSONs → flat dataframe
│   ├── 02_eda.ipynb                 ← Exploratory data analysis
│   ├── 03_position_bias.ipynb       ← Core analysis: position vs runs
│   ├── 04_playoff_bias.ipynb        ← Matches played disadvantage analysis
│   └── 05_visualizations.ipynb     ← All final charts for the paper
│
├── src/
│   ├── parse_cricsheet.py      ← JSON parser → pandas DataFrame
│   ├── features.py             ← Derived field calculations
│   ├── stats.py                ← Statistical tests (t-tests, correlations)
│   └── visualize.py            ← Reusable chart functions
│
├── outputs/
│   ├── figures/                ← Final charts (PNG/SVG) for paper
│   └── tables/                 ← Summary stat tables (CSV/LaTeX)
│
├── paper/
│   ├── draft_v1.md             ← Paper draft in Markdown
│   └── references.bib          ← Bibliography
│
└── requirements.txt
```

---

## Analysis Pipeline (Step by Step)

### Step 1 — Data Ingestion (`01_data_ingestion.ipynb`)
**Goal:** Parse all IPL match JSONs into a single flat ball-by-ball DataFrame

```python
# Expected output schema
columns = [
    'match_id', 'season', 'date', 'match_stage',   # match metadata
    'batting_team', 'bowling_team',                  # teams
    'innings', 'over', 'ball',                       # ball position
    'batter', 'bowler',                              # players
    'runs_batter', 'runs_extras', 'runs_total',      # runs
    'is_wicket', 'wicket_kind',                      # dismissals
    'batting_position',                              # derived
    'phase',                                         # derived: powerplay/middle/death
    'match_result', 'winner'                         # outcome
]
```

**Notes for Claude Code:**
- Handle both old and new Cricsheet JSON schemas (format changed slightly over years)
- `batting_position` = order of arrival at the crease in that innings, tracked from
  both the `batter` (striker) and `non_striker` fields so a non-striking batter who
  enters before facing a ball (e.g. an opener whose partner is dismissed first) keeps
  their true position
- Some matches have DLS adjustments — include but flag them
- Save output as `data/processed/ball_by_ball.parquet`

---

### Step 2 — Reference Data (`data/reference/orange_cap_winners.csv`)
**Goal:** A clean lookup table of every Orange Cap winner

```csv
season,winner,team,total_runs,matches_played,avg_batting_position,playoff_team
2008,Shaun Marsh,Kings XI Punjab,616,11,1.0,No
2009,Matthew Hayden,Chennai Super Kings,572,12,1.0,Yes
2010,Sachin Tendulkar,Mumbai Indians,618,15,1.0,Yes
2011,Chris Gayle,Royal Challengers Bangalore,608,13,1.0,No
2012,Chris Gayle,Royal Challengers Bangalore,733,15,1.0,No
2013,Michael Hussey,Chennai Super Kings,733,17,1.0,Yes
2014,Robin Uthappa,Kolkata Knight Riders,660,16,1.5,Yes
2015,David Warner,Sunrisers Hyderabad,562,14,1.0,Yes
2016,Virat Kohli,Royal Challengers Bangalore,973,16,3.0,Yes
2017,David Warner,Sunrisers Hyderabad,641,14,1.0,Yes
2018,Kane Williamson,Sunrisers Hyderabad,735,17,3.0,Yes
2019,David Warner,Sunrisers Hyderabad,692,12,1.0,Yes
2020,KL Rahul,Kings XI Punjab,670,14,1.0,No
2021,Ruturaj Gaikwad,Chennai Super Kings,635,16,1.0,Yes
2022,Jos Buttler,Rajasthan Royals,863,17,1.0,Yes
2023,Shubman Gill,Gujarat Titans,890,17,1.0,Yes
2024,Virat Kohli,Royal Challengers Bangalore,741,15,3.0,Yes
2025,Sai Sudharsan,Gujarat Titans,759,15,2.0,Yes
```

**Note:** Verify and update `avg_batting_position` from the actual Cricsheet data
during analysis. The values above are approximate starting points.

---

### Step 3 — Batter-Season Aggregation (`features.py`)
**Goal:** One row per batter per season with all key metrics

```python
# Expected output schema
batter_season_columns = [
    'season', 'batter',
    'total_runs', 'total_balls', 'innings_count', 'matches_played',
    'strike_rate', 'batting_average',
    'avg_batting_position', 'position_group',        # Opener/TopOrder/Middle/Finisher
    'powerplay_runs', 'middle_runs', 'death_runs',   # runs by phase
    'powerplay_balls', 'middle_balls', 'death_balls', # balls by phase
    'playoff_team',                                   # boolean
    'orange_cap_winner'                               # boolean
]
```

---

### Step 4 — Core Statistical Analysis (`03_position_bias.ipynb`)

#### Analysis A: Orange Cap Winner Position Distribution
- For all 19 seasons (2008–2026), what batting position did the winner bat at?
- Expected finding: ~90%+ batted at positions 1–3
- Statistical test: Chi-square test — is the distribution of winner positions
  significantly different from the overall distribution of run-scorers?

#### Analysis B: Balls Faced by Position Group
- Compare average balls faced per season across position groups
- Expected finding: Openers face ~40–60% more balls than middle-order batsmen
- Statistical test: One-way ANOVA or Kruskal-Wallis across position groups

#### Analysis C: Powerplay Run Concentration
- What % of total seasonal runs does each position group score in the powerplay?
- Expected finding: Openers score 30–50% of their runs in powerplay;
  middle order scores ~0–5%
- Visualize as stacked bar chart by position group

#### Analysis D: The "If Normalized" Counterfactual
- For each season, take the top-10 run-scorers
- Normalize their runs to a standard 14-match season (league stage only)
- Re-rank — how often does the Orange Cap winner change?
- This is the most compelling finding for the paper

---

### Step 5 — Playoff Bias Analysis (`04_playoff_bias.ipynb`)

#### Analysis E: Match Count Advantage
- League stage = 14 matches for all teams
- Playoff teams play 1–3 additional matches
- Calculate: what is the average extra run contribution from playoff matches
  for Orange Cap winners?
- If a winner's playoff runs > margin of victory over #2, playoff access
  was the deciding factor

#### Analysis F: Non-Playoff Elite Batsmen
- Identify seasons where a non-playoff team batter ranked in top 5 overall
- Project their runs if they had played the same number of matches as the winner
- Named examples make this analysis more compelling for readers

---

### Step 6 — Visualizations (`05_visualizations.ipynb`)

All charts should be publication-quality (300 DPI, clean style, labeled axes).

| Chart | Type | Key Message |
|---|---|---|
| Orange Cap winners by batting position (2008–2026) | Bar chart | ~90% are openers/top 3 |
| Balls faced per season by position group | Box plot | Openers face far more balls |
| Runs by phase by position group | Stacked bar | Openers monopolize powerplay |
| Runs vs batting position scatter (all seasons) | Scatter | Strong negative correlation |
| Normalized runs ranking vs actual ranking | Dot plot | Rankings shift when normalized |
| Match count: league vs playoff teams | Bar | Playoff teams play more |

**Style:** Use matplotlib with a clean academic style. No seaborn dark backgrounds.
Export as both PNG (for draft) and SVG (for final submission).

---

## Paper Structure (Draft Outline)

### 1. Abstract (~250 words)
- Problem: Orange Cap rewards volume, not quality
- Method: Ball-by-ball analysis of all IPL seasons (2008–2026)
- Finding: Structural bias against middle-order batsmen and non-playoff teams
- Implication: Award criteria need reform

### 2. Introduction
- Brief IPL background
- What the Orange Cap is and its current criteria
- Why this matters (fairness in sport, award design)
- Paper structure roadmap

### 3. Literature Review
- Existing cricket performance indices (DPI, DPPI)
- Batting position research in T20 cricket
- Award fairness in other sports analytics contexts
- Gap: no paper specifically challenges Orange Cap fairness

### 4. Data & Methodology
- Cricsheet data description (1,243 matches, 2008–2026)
- Variable definitions (batting position, phase, playoff team)
- Statistical methods used

### 5. Results
- 5.1 Batting position of Orange Cap winners (historical)
- 5.2 Balls faced inequality across position groups
- 5.3 Powerplay access concentration
- 5.4 Playoff match advantage
- 5.5 Normalized rankings counterfactual

### 6. Discussion
- Implications for award design
- Limitations of current study
- Teaser for Paper 2 (proposed Best Batsman Index)

### 7. Conclusion

### 8. References

---

## Target Journals & Conferences

### Primary Targets
| Venue | Type | Why |
|---|---|---|
| Journal of Sports Analytics (IOS Press/SAGE) | Journal | Published T20 cricket metrics papers; strong fit |
| International Journal of Sports Science & Coaching | Journal | Published systematic reviews on cricket ranking |
| MIT Sloan Sports Analytics Conference | Conference | Cricket analytics has won awards here |
| Carnegie Mellon Sports Analytics Conference | Conference | More accessible; good stepping stone |

### Secondary Targets
| Venue | Type | Notes |
|---|---|---|
| Wharton Sports Analytics Journal | Journal | Growing T20 cricket focus |
| MDPI Applied Sciences | Journal | Open access, faster review cycle |
| PCCDA (Springer Nature) | Conference | Has published IPL ML research |

---

## Tech Stack

```
Language:     Python 3.11+
Data:         pandas, numpy
Storage:      parquet (via pyarrow), DuckDB for large JSON processing
Viz:          matplotlib (primary), seaborn (secondary)
Stats:        scipy.stats (t-tests, ANOVA, chi-square)
Notebook:     Jupyter Lab
Version ctrl: Git
```

### requirements.txt
```
pandas>=2.0.0
numpy>=1.24.0
pyarrow>=12.0.0
duckdb>=0.9.0
matplotlib>=3.7.0
seaborn>=0.12.0
scipy>=1.11.0
jupyter>=1.0.0
requests>=2.31.0
tqdm>=4.65.0
```

---

## Key Decisions & Constraints

| Decision | Choice | Reason |
|---|---|---|
| Seasons to analyze | 2008–2026 (19 seasons) | Complete seasons; 2026 concluded 2026-05-31 |
| Minimum innings threshold | 7+ innings to qualify | Avoids small-sample noise |
| Batting position definition | Crease-arrival order (striker + non_striker) per innings | Avoids mislabelling non-striking openers whose partner is dismissed first |
| Phase boundaries | PP=1–6, Middle=7–15, Death=16–20 | Standard IPL convention |
| Playoff definition | Any team appearing in Qualifier 1/2 or Eliminator | Consistent across all seasons |
| Statistical significance threshold | p < 0.05 | Standard academic convention |

---

## What to Ask Claude Code

When working on this project, Claude Code should be able to help with:

- **Parsing:** "Parse all IPL JSONs from `data/raw/ipl_json/` into a flat DataFrame"
- **Features:** "Add `batting_position` and `phase` columns to the ball-by-ball DataFrame"
- **Analysis:** "Run a Kruskal-Wallis test comparing balls faced across position groups"
- **Visualization:** "Create a publication-quality box plot of balls faced by position group"
- **Writing:** "Draft the methodology section based on the analysis in notebook 03"
- **Validation:** "Cross-check our season run totals against the reference CSV"

---

## Current Status

- [x] Research question defined
- [x] Literature review scoped
- [x] Data source confirmed (Cricsheet)
- [x] Analysis plan designed
- [x] Paper structure outlined
- [x] Target journals identified
- [ ] Data downloaded and parsed
- [ ] Reference Orange Cap winners CSV finalized
- [ ] EDA complete
- [ ] Core analyses complete
- [ ] Visualizations finalized
- [ ] Paper draft written
- [ ] Peer review / submission

---

## Notes & Open Questions

1. **2026 data:** IPL 2026 is ongoing — exclude from analysis or include as partial?
   → Decision (2026-06-02): 2026 season completed (final 2026-05-31) and is now
   included. Scope is 2008–2026 (19 complete seasons).

2. **Batting position volatility:** Some players change positions match to match
   (e.g. Kohli sometimes opened, sometimes at #3). Use average position across
   the season or mode?
   → Decision: Use average batting position per season; report both if they differ

3. **Impact Player rule (2023+):** IPL introduced the Impact Player substitution
   rule in 2023, which can affect batting positions. Flag this as a limitation.

4. **DLS-affected matches:** A handful of matches are shortened by rain. Include
   but flag — they affect balls faced calculations.

5. **Tiebreaker for Orange Cap:** If two players are tied on runs, the player with
   higher strike rate wins. Noted — relevant for counterfactual analysis.
