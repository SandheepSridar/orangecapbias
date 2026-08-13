# TNPL ball-by-ball data & full bias analysis

**All 9 seasons (2016–2025) are scraped, validated, and analysed.** The complete
IPL Orange Cap bias pipeline + MOVI has been replicated on TNPL — findings in
`tnpl_analysis.md`, tables in `tables/`, figures (fig1–fig7) in `figures/`,
validation in `data_quality_report_all.md`. Pipeline:
`prepare_data.py → build_tables.py → stats.py → middle_order_index.py →
visualize.py` (see tnpl_analysis.md for commands). Reference award data
(Wikipedia, corrected): `reference_awards.csv`.

**2026 season (in progress, added 2026-08-12):** `tnpl_2026_bbb.csv` /
`tnpl_2026_matches.csv` have the 15 matches played so far (of 32 scheduled —
league stage still running, playoffs TBC). Included in the combined
`tnpl_ball_by_ball.csv` (via `prepare_data.py`, which auto-discovers every
`tnpl_*_bbb.csv`), but **deliberately not** run through `build_tables.py` /
`stats.py` / `middle_order_index.py` / `visualize.py` / `data_quality_all.py`
— those are built around complete seasons (`data_quality_all.py` cross-checks
a hardcoded season list against `reference_awards.csv`'s finalized Most Runs
winners, which don't exist yet for a season still in progress) and blending a
partial season into the published findings/figures needs an explicit call,
not a silent default. Validated with the single-season `data_quality.py 2026`
instead — clean, modulo two data-source quirks consistent with patterns
already documented below (a handful of `otherBatsman` refs to athlete id `0`
on specific deliveries, one wicket without a flagged dismissal kind) — see
`data_quality_report.md`. Re-run this section's scrape commands to pick up
newly-played matches as the season continues.

**`site.api.espn.com` is now Akamai-blocked (discovered 2026-08-12, confirmed
on both new and previously-working match ids — a global change, not specific
to 2026).** `scrape_match.py` no longer uses it: match metadata, team names,
and player names are now all sourced from `core.espnuk.org` endpoints instead
(events/status/teams/athletes — see the docstring in `scrape_match.py`), with
player/team name lookups cached in shared `raw/athletes/` and `raw/teams/`
directories (not per-match, since the same ids recur across a whole season).
One knock-on fix: `prepare_data.py`'s `player_team_map()` used to read the
now-gone `raw/{match}/summary.json` for the batter→team mapping; it now falls
back to deriving the same mapping from the cached per-ball detail JSONs
(which already carry a team ref per batter) when `summary.json` is absent —
2016–2025 data still uses the original summary.json path unchanged.

---

## Feasibility notes (original prototype)

**Question:** is Cricsheet-style ball-by-ball data obtainable for the Tamil Nadu
Premier League?
**Answer (2026-06-11): yes** — not from Cricsheet (TNPL isn't covered), but from
ESPN's public core API, which has full per-delivery data for all TNPL seasons.

## What works

ESPNcricinfo's own JSON APIs (`hs-consumer-api.espncricinfo.com`,
`/matches/engine/...json`) are Akamai bot-blocked (403). ESPN's generic sports
APIs are open and serve the same underlying data:

| Purpose | Endpoint |
|---|---|
| Seasons (9, 2016–2025) | `core.espnuk.org/v2/sports/cricket/leagues/1047323/seasons` |
| Matches in a season | `core.espnuk.org/v2/sports/cricket/leagues/{seriesId}/events?dates={year}&limit=300` |
| Match summary, rosters (player names) | `site.api.espn.com/apis/site/v2/sports/cricket/{seriesId}/summary?event={matchId}` |
| Ball-by-ball (refs, 1/delivery) | `core.espnuk.org/v2/sports/cricket/leagues/1047323/events/{matchId}/competitions/{matchId}/plays?limit=300` |

TNPL's umbrella league id is `1047323`. Each season also has its own series id
(2025 = `1489106`, 2024 = `1439628`, ...), discoverable from the seasons
endpoint. TNPL 2025 lists 32 matches (28 league + 4 playoffs).

Each delivery record has: innings, over.number, over.ball, batsman/bowler
athlete ids (names resolve via the summary rosters), play type, running team
score, boundary flag, and dismissal details — enough to build the same
schema as `data/processed/ball_by_ball.parquet`.

## Data-quality gotchas

- **`scoreValue` undercounts compound extras** — a "no ball + 4 byes" delivery
  carried `scoreValue: 1`. Derive `runs_total` from the *running team score
  delta*, which reconciles exactly with published scorecards.
- **`dismissal` can miss a wicket** — the final wicket ball jumped the score
  from 98/8 to 102/10 with only one flagged dismissal. Derive `is_wicket` from
  the running wicket delta too.
- **`homeScore`/`awayScore` are misnamed** — in the plays feed, `homeScore`
  tracks the side batting *first* and `awayScore` the side batting *second*,
  regardless of who is actually home/away. Mapping by the rosters' homeAway
  flag silently zeroes out matches where the away team bats first (14 of 32
  in 2025).
- Over numbering is 1-based (over 15 ball 4 = cricket "14.4").
- Occasional transient 502/503s — retry with backoff; the on-disk cache makes
  re-runs cheap and resumable.

## Scripts & data

```bash
python3 TNPL/scrape_match.py [matchId]          # one match -> bbb_{matchId}.csv
python3 TNPL/scrape_season.py [seriesId year]   # whole season (default 1489106 2025)
python3 TNPL/data_quality.py [year]             # checks -> data_quality_report.md
```

`tnpl_2025_bbb.csv` holds the full 2025 season (32 matches, 7,439 deliveries;
~9 min scrape) with `tnpl_2025_matches.csv` as the match index. Raw JSON is
cached in `raw/{matchId}/` (gitignored).

**Validation status (2025): all checks pass** — no structural anomalies, all
64 innings totals reconcile exactly with official scores, and the season run
leader matches espncricinfo's report (Tushar Raheja 488 runs, SR 186). See
`data_quality_report.md`.

## Scaling to all seasons

~9 seasons × ~32 matches ≈ 60–65k requests ≈ 1.5 h, fully resumable thanks to
the on-disk cache. Per-season series ids come from the seasons endpoint.
Check ESPN's terms of use before publishing research built on this data.
