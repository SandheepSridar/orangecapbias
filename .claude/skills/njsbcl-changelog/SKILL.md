---
name: njsbcl-changelog
description: Update NJSBCL/dashboard/changelog.html with human-readable entries for NJSBCL dashboard feature work done since the last recorded entry, newest date first. Use when Sandheep asks to "update the NJSBCL changelog", "add this to the changelog", or after a session that added/changed a feature on the NJSBCL dashboard (index.html, charts.html, app.js, charts.js, build_data.py, styles.css).
user-invocable: true
---

# NJSBCL changelog

Keeps `NJSBCL/dashboard/changelog.html` (a real page on the dashboard, linked from
the nav on `index.html` and `charts.html`) up to date with what's changed, in
**descending date order** (newest date block at the top; newest entry at the
top within a date block too).

## Step 1 — find what's new

Read `NJSBCL/dashboard/changelog.html` and find the marker near the top of
`#sec-changelog`:

```html
<!-- last-recorded-commit: <short-hash> -->
```

Then get every commit since that marker touching the dashboard:

```bash
git log <short-hash>..HEAD --reverse --pretty=format:"%h|%ad|%s" --date=format:"%Y-%m-%d %H:%M" -- NJSBCL
```

If there's nothing new, say so and stop — don't touch the file.

## Step 2 — turn commits into real descriptions, not commit messages

Commit messages in this repo are terse ("update", "roster added with fixes",
"more details on upcoming fixtures") — never copy them into the changelog
verbatim. For each commit, look at what actually changed
(`git show --stat <hash> -- NJSBCL`, and the diff itself for anything
ambiguous) and write a one-liner in this style, matching the existing entries
in the file:

```html
<li><b>Short feature name</b> — one sentence on what it does or shows, written for someone using the site, not someone reading a diff.</li>
```

Skip commits that don't change what a user of the site sees or can do:
data-only refreshes (e.g. a `rescrape-njsbcl` run that only touches
`data.js`), `.gitignore`/README-only edits, pure formatting/typo fixes. Only
log genuine feature additions, UI changes, or methodology changes — same bar
as what's already in the file.

If several commits are really one feature landing in pieces (e.g. a feature
commit immediately followed by a "fixes" commit for the same thing), collapse
them into a single bullet rather than listing both.

## Step 3 — insert in descending date order

Group the new commits by **calendar date** (from the commit date, already
`%Y-%m-%d` above). For each date, newest commit first within that date.

- If the newest new date is **not** already the top block in the file, insert
  a whole new `.changelog-day` block at the very top of `#sec-changelog`
  (right after the marker comment), above the existing top block. Repeat for
  each additional new date, in descending order, so the final order top-to-
  bottom is newest date → oldest date.
- If the newest new date **matches** the file's current top date block (e.g.
  you're re-running this later the same day), prepend the new `<li>` bullets
  to the top of that existing block's `<ul class="changelog-list">` instead
  of creating a second heading for the same day.

Match the exact date heading format already used: `<h2 class="changelog-date">Thu, Aug 13 2026</h2>`.

Never edit or delete existing date blocks/entries — this is additive history.

## Step 4 — update the marker

Move the `<!-- last-recorded-commit: ... -->` comment to the new HEAD commit
hash for `NJSBCL` (`git log -1 --format=%h -- NJSBCL`).

## Notes

- This skill only edits `NJSBCL/dashboard/changelog.html`. It never touches
  `build_data.py`, `data.js`, or regenerates any data — the changelog is
  purely a static, hand-curated page of past feature work.
- The page has no JS data layer by design (unlike the rest of the dashboard,
  which recomputes from `data.js`) — changelog content doesn't need
  client-side filtering or interactivity, so plain static HTML blocks kept it
  simple. Don't introduce a `changelog.js`/data-driven renderer for this
  unless Sandheep specifically asks for interactive filtering.
- Styling lives in `styles.css` under `/* ── Changelog ── */`
  (`.changelog-day`, `.changelog-date`, `.changelog-list`) — reuse it, don't
  add new one-off styles per entry.
