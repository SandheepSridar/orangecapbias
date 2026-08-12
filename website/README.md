# MOVI website

Static, share-only site for the Middle-Order Value Index — same public scope as
`app_movi.py` (no exact formula/weights, no Orange Cap bias study internals).
Pure HTML/CSS/JS, no build step, no server-side code.

## Files

- `index.html`, `styles.css`, `app.js` — the site
- `data.js` — generated data (raw middle-order components, season run-leaders,
  award recognition); MOVI is recomputed live in the browser, so the threshold
  controls re-score the whole index just like the Streamlit app
- `build_data.py` — regenerates `data.js` from the project CSVs

## Updating data

After re-running the analysis pipeline:

```bash
uv run --with pandas python website/build_data.py
```

## Viewing / deploying

Open `index.html` directly, or serve locally:

```bash
python3 -m http.server -d website 8000
```

Deploys as-is to any static host (GitHub Pages, Netlify, etc.).
