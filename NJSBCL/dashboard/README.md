# NJSBCL Scout — competition-analysis dashboard

Static site (no build step, no framework) modeled on `../../website/` (MOVI).
Pick a series (Division 1 / Weekenders Cup) and an opponent — everything else
(toss advice, top batsmen/bowlers, dismissal breakdowns, head-to-head,
upcoming fixtures) updates for that matchup.

## View it

```
python3 -m http.server 8834
```
then open http://localhost:8834/index.html — or just double-click
`index.html`, no server required.

## Regenerate data.js after a fresh scrape

```
source ../.venv/bin/activate   # first time: python3 -m venv ../.venv && pip install pandas openpyxl
python3 build_data.py
```

`build_data.py` reads the scraped CSVs/schedule exports in `../data/` and
precomputes everything into `data.js` — nothing is computed from raw data at
page-load time except the display logic itself.

**Why final scores come from `division1_true_totals.csv` /
`weekenderscup_true_totals.csv` and not the scorecard batting rows:** summing
individual batters' runs excludes extras, which run 10–20 runs/innings in
this league — enough to flip real results. Those two CSVs hold the official
score1/score2 per match scraped from the listMatches.do result blocks.
