# TNPL MOVI website

Static, share-only site for TNPL's Middle-Order Value Index — same format and
scope as the IPL version (`website/`): no exact formula/weights, no bias study
internals. Pure HTML/CSS/JS, no build step, no server-side code.

## Files

- `index.html`, `styles.css`, `app.js` — the main site (2016–2025, 9 complete seasons)
- `data.js` — generated data (raw middle-order components, season run-leaders,
  award recognition); MOVI is recomputed live in the browser, so the threshold
  controls re-score the whole index
- `build_data.py` — regenerates `data.js` from `TNPL/tables/` CSVs
- `2026.html`, `app_2026.js`, `data_2026.js`, `build_data_2026.py` — a separate,
  clearly-labelled **provisional** page for the in-progress 2026 season (linked
  from the main page's hero). Recomputes the same v1 MOVI methodology from
  `tnpl_ball_by_ball.csv` filtered to season 2026 only. No champions/dumbbell/
  recognition sections — those need a finished season (final awards aren't
  decided yet) — just the live leaderboard and a strike-rate note.

## Updating data

Main index, after re-running the TNPL analysis pipeline (`prepare_data.py →
build_tables.py → stats.py → middle_order_index.py`, see `TNPL/README.md`):

```bash
uv run --with pandas python3 TNPL/website/build_data.py
```

Covers the 9 complete seasons (2016–2025) only — 2026 is still in progress and
excluded, same as `TNPL/tables/middle_order_components.csv` itself.

2026 page, after re-running `TNPL/scrape_season.py` + `TNPL/prepare_data.py`
to pick up newly-played matches:

```bash
uv run --with pandas python3 TNPL/website/build_data_2026.py
```

**When the 2026 season concludes:** run it through the main pipeline
(`build_tables.py`, `middle_order_index.py`) like any other complete season,
regenerate `data.js` via `build_data.py`, and retire `2026.html` / `data_2026.js`
/ `app_2026.js` / `build_data_2026.py` — the season becomes part of the main
index instead of a separate provisional page.

## Viewing / deploying

Open `index.html` directly, or serve locally:

```bash
python3 -m http.server -d TNPL/website 8000
```

Deploys as-is to any static host (GitHub Pages, Netlify, etc.).
