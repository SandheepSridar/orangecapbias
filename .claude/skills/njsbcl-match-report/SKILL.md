---
name: njsbcl-match-report
description: Generate a PDF scouting/intelligence report for the next upcoming NJSBCL match (whichever series it's in) from everything already in the dashboard's data.js, and save it to ~/Downloads. Use when Sandheep asks to "make a scouting report", "PDF for the next match", "match intelligence report", or similar.
user-invocable: true
---

# NJSBCL match intelligence PDF report

Builds a print-ready PDF report — win probability, toss advice, opponent's key
batsmen/bowlers, bowling battle, recent form, and our own squad's win-dependency
appendix — for whichever match is soonest across **both** series (Division 1 and
Weekenders Cup), and saves it to `~/Downloads`.

This does **not** re-scrape anything. It's built entirely from
`NJSBCL/dashboard/data.js` as it currently stands — the same data the dashboard
itself shows. If that's stale, run the `rescrape-njsbcl` skill first (don't do
this automatically; ask Sandheep, since it's a 20-30 minute interactive scrape).

## Steps

1. `cd NJSBCL/dashboard/report`
2. `node extract_report_data.js` — reads `../data.js`, compares both series'
   `upcoming[0]` fixture dates, picks whichever is soonest, and writes
   `report_data.json` (our team, the opponent, our squad-wide charts data for
   that series). Prints which match it picked — sanity-check this matches what
   Sandheep expects before moving on (e.g. if he specifically wants the
   *Division 1* match and Weekenders happens to be sooner, tell him and ask
   which one he wants — don't just silently pick the earliest).
3. `uv run --with fpdf2 python3 build_pdf.py` — reads `report_data.json`, builds
   the PDF, and saves it to
   `~/Downloads/NJSBCL_Scout_Report_<Opponent>_<Date>.pdf`. Prints the full path
   on success.
4. Tell Sandheep the file landed in Downloads with its exact filename.

## Files

- `extract_report_data.js` — Node, no dependencies. Bridges `data.js` (JS, not
  JSON — same `new Function(src).call()` trick used elsewhere in this project
  for one-off data.js introspection) into a plain JSON snapshot for Python to
  consume.
- `build_pdf.py` — Python + `fpdf2` (fetched on demand via `uv run --with
  fpdf2`, no persistent install needed). All layout logic lives in a `Report`
  subclass of `FPDF`.
- `report_data.json` — regenerated fresh each run by step 2; not meant to be
  committed or hand-edited.

## fpdf2 gotchas already solved here — preserve these if you touch build_pdf.py

- **Core fonts (Helvetica/Times/Courier) are Latin-1 only.** The dashboard's
  copy uses em dashes and curly quotes that would raise an encoding error or
  render as garbage. Every string goes through `clean()` first, which swaps
  those for ASCII equivalents. Don't bypass it by calling `self.cell()` /
  `self.multi_cell()` directly with raw data — always pass through `clean()`
  (the `Report` helper methods already do this internally).
- **`rect()` doesn't participate in auto-page-break.** A manually-drawn box
  (used for the "callout" stat cards) can end up on one page while text drawn
  inside it via `set_xy()`/`multi_cell()` spills onto the next — the box
  border and its content visibly separate. Fixed by `_ensure_space()`: check
  if the estimated block height fits before the page-break trigger, and force
  `add_page()` first if not, so the whole box is always atomic on one page.
  `callout()` and `table()` both call this before drawing anything.
- **A `subhead()` immediately followed by a `table()` can orphan** — the
  heading fits at the bottom of a page, the table it belongs to gets pushed to
  the next. Use `subhead_table()` (reserves the combined height first) instead
  of calling `subhead()` + `table()` back to back.
- **Plain `cell()` does not wrap — it overflows into the next column** if the
  text is wider than the cell. Dismissal-type breakdowns (e.g. a batsman with
  4+ ways of getting out) can hit this. `dismissal_line()` caps at 3 types
  with a "(+N more)" suffix specifically to avoid it. If you add a new table
  column with potentially-long freeform text, either cap it similarly or
  switch that cell to `multi_cell` and recompute row height per-row.
- Two-column side-by-side tables (tried initially for the Best XI list) are
  **not worth it** — independent page-break flows between the two columns
  desync badly if either overflows. Just use one full-width table; the
  content here is short enough (11 rows max) that a single column is never a
  real space problem.
