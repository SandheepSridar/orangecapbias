# TNPL MOVI website

Static, share-only site for TNPL's Middle-Order Value Index — same format and
scope as the IPL version (`website/`): no exact formula/weights, no bias study
internals. Pure HTML/CSS/JS, no build step, no server-side code.

## Files

- `index.html`, `styles.css`, `app.js` — the site
- `data.js` — generated data (raw middle-order components, season run-leaders,
  award recognition); MOVI is recomputed live in the browser, so the threshold
  controls re-score the whole index
- `build_data.py` — regenerates `data.js` from `TNPL/tables/` CSVs

## Updating data

After re-running the TNPL analysis pipeline (`prepare_data.py → build_tables.py
→ stats.py → middle_order_index.py`, see `TNPL/README.md`):

```bash
uv run --with pandas python3 TNPL/website/build_data.py
```

Covers the 9 complete seasons (2016–2025) only — 2026 is still in progress and
excluded, same as `TNPL/tables/middle_order_components.csv` itself.

## Viewing / deploying

Open `index.html` directly, or serve locally:

```bash
python3 -m http.server -d TNPL/website 8000
```

Deploys as-is to any static host (GitHub Pages, Netlify, etc.).
