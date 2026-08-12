---
name: rescrape-njsbcl
description: Re-scrape 2026 Division 1 and Weekenders Cup data from cricclubs.com/NJSBCL (match scorecards, true totals, schedules) and rebuild the NJSBCL Scout dashboard's data.js. Use when Sandheep asks to "rescrape NJSBCL", "update the cricket data", "refresh the dashboard data", or similar. Must run interactively in a session with Claude in Chrome connected to Sandheep's real, logged-in browser — see "Why this can't be automated" below.
user-invocable: true
---

# Rescrape NJSBCL data

Full re-scrape of both series (2026 Division 1, 2026 Weekenders Cup) from
cricclubs.com/NJSBCL and rebuild `NJSBCL/dashboard/data.js`. Takes ~20-30
minutes of tool calls. Re-run in full each time — don't try to scrape
incrementally, it's not worth the complexity at this data volume.

## Why this can't be automated / run unattended

cricclubs.com sits behind Cloudflare bot detection that blocks headless or
freshly-automated browsers outright (confirmed: a Playwright-launched profile
got stuck on Cloudflare's "Performing security verification" screen
indefinitely, even after real login attempts). The only thing that reliably
gets through is **Sandheep's own real, already-logged-in Chrome**, driven via
the claude-in-chrome extension. That means:
- This skill must be run **interactively**, in a session where Claude in
  Chrome is connected and Sandheep is logged into cricclubs.com/NJSBCL.
- It **cannot** run as a cloud-scheduled/background agent — there's no
  browser to drive there.
- Even within a real browser, rapid/bulk `fetch()` calls trip Cloudflare's
  rate limiter after roughly 30-60 requests in quick succession. Real page
  **navigations** don't seem to trip it the same way (used to recover — see
  below). Stay within the batch sizes and delays given here; if you get
  ambitious and enlarge them, expect to eat a Cloudflare block and have to
  recover via navigation + wait.

## Prerequisites

1. Load browser tools if deferred: `ToolSearch("select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__find")`.
2. Get tab context, create a new tab, navigate to `https://cricclubs.com/NJSBCL`. Confirm a
   "Logout" link is present (i.e. Sandheep is logged in). If not, stop and ask him to log in —
   never attempt this yourself.
3. Confirm Chrome's automatic-downloads permission for `cricclubs.com` is still allowed (it was
   granted once already — check `chrome://settings/content/automaticDownloads`). If downloads
   silently stop landing in `~/Downloads` partway through, this is almost always why; ask
   Sandheep to re-add the site rather than trying to work around it.
4. `clubId=2690` always. Series: `league=58` = 2026 Division 1, `league=60` = 2026 Weekenders Cup.

## The core technique: blob-download, not chat relay

**Never** try to return large scraped payloads through a tool call's text result — the harness
truncates it at ~900-1000 chars and a content filter can silently eat a chunk. Instead, inside
the page via `javascript_tool`, build a `Blob`, `URL.createObjectURL`, and click a synthetic
`<a download>` — this writes an exact, complete file straight to `~/Downloads`, no chat relay,
no truncation. Then `mv` it into `NJSBCL/data/` via Bash. This is the pattern for everything
below.

## Step 1 — True match totals (do this first, it's fast and everything else depends on it)

**Why not just sum the batting scorecard rows:** summing individual batters' runs excludes
extras, which run 10-20 runs/innings in this league — enough to flip real results. Get the
official score from `listMatches.do`'s result blocks instead.

For each series (`league=58` then `league=60`):

```js
// navigate to https://cricclubs.com/NJSBCL/listMatches.do?clubId=2690&league=<58|60> first,
// wait ~3-5s (Cloudflare's JS challenge needs a moment to clear on a fresh navigation —
// if document.title is "Just a moment..." after navigating, just wait longer, it clears itself)
function clean(s){return s.replace(/\s+/g,' ').trim();}
const blocks=[...document.querySelectorAll('.team-data')];
const re = /(\d+)\/(\d+)\s+[\d.]+\/\d+\s+(\d+)\/(\d+)\s+[\d.]+\/[\d.]+/;
const rows = [];
for (const b of blocks) {
  const link = b.querySelector('a[href*="viewScorecard"]');
  const m = link ? link.getAttribute('href').match(/matchId=(\d+)/) : null;
  if (!m) continue;
  const text = clean(b.innerText);
  const sm = text.match(re);
  if (!sm) { rows.push([m[1], 'NOMATCH']); continue; }
  rows.push([m[1], sm[1], sm[2], sm[3], sm[4]]);
}
window.__totals = rows;
JSON.stringify({total: rows.length, nomatch: rows.filter(r=>r[1]==='NOMATCH').length});
```

Check `nomatch` is 0 (it always has been — if not, inspect what changed on the page before
proceeding). Then download:

```js
const csv = 'matchId,score1,wkts1,score2,wkts2\n' + window.__totals.map(r=>r.join(',')).join('\n');
const blob = new Blob([csv], {type:'text/csv'});
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url; a.download = 'true_totals.csv';
document.body.appendChild(a); a.click(); a.remove();
```

Move to `NJSBCL/data/division1_true_totals.csv` (or `weekenderscup_true_totals.csv`). This page
in one fetch gives every match in the series (300ish for D1, 600 for Weekenders — no need to
filter to a bracket here, the scorecard step below will only ever request matchIds it needs).

## Step 2 — Full scorecards (batting + bowling)

Still on `listMatches.do` for the series, get the matchId list you'll actually need:
- **Division 1**: every matchId on the page (all ~300 — it's a single A-vs-B cross-play format,
  there's no smaller "our bracket" subset).
- **Weekenders Cup**: VRK Gladiators only plays Group A vs Group D. Filter blocks to matches
  containing at least one Group A or Group D team name before extracting matchIds (~285 of the
  600). Get the current Group A/D team names from the existing
  `NJSBCL/data/weekenderscup_batting_all_teams.csv` `Group` column if that file's still around,
  otherwise re-derive from the team list page — group assignments don't change mid-season.

```js
const links=[...document.querySelectorAll('a[href*="viewScorecard"]')];
const ids=[...new Set(links.map(a=>{const m=a.getAttribute('href').match(/matchId=(\d+)/);return m?m[1]:null;}).filter(Boolean))];
window.__ids = ids;  // filter this array down first for weekenders, per above
```

Now define the fetch+parse function **once** (this is the corrected version — an earlier attempt
got bowling-team attribution backwards, crediting bowling figures to the team that had just
*batted* instead of the team that was fielding; this version fixes that by doing a two-pass read
of the batting-innings headers first). It also captures extras: the bowling table's 8th cell is a
string like `(2 w)` or `(1 w 1 nb)` — wides/no-balls bowled by that bowler, parsed out separately
so `build_data.py` can compute the "bowlers to target" weakness metric (economy + worst-spell
economy + extras rate):

```js
function clean(s){ return s.replace(/\s+/g,' ').trim(); }
function csvEscape(s){ s=String(s??''); if(/[",\n]/.test(s)) return '"'+s.replace(/"/g,'""')+'"'; return s; }
function parseExtras(s){
  s = clean(s||'');
  const wm = s.match(/(\d+)\s*w/);
  const nm = s.match(/(\d+)\s*nb/);
  return [wm?wm[1]:'0', nm?nm[1]:'0'];
}
async function fetchScorecard(matchId){
  const url = `https://cricclubs.com/NJSBCL/viewScorecard.do?matchId=${matchId}&clubId=2690`;
  const res = await fetch(url);
  if (res.status !== 200) return {battingRows:[], bowlingRows:[], blocked:true, status:res.status};
  const html = await res.text();
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const tables = [...doc.querySelectorAll('table.table')];
  function isBattingHeader(t){
    const firstRowText = clean(t.querySelector('tr')?.innerText || '');
    const headerCells = [...(t.querySelector('tr')?.children||[])].map(c=>clean(c.innerText));
    return /innings/i.test(firstRowText) && headerCells.length>=6 ? firstRowText.split(/\s+innings/i)[0].trim() : null;
  }
  const teams = tables.map(isBattingHeader).filter(Boolean);
  const battingRows = [];
  const bowlingRows = [];
  let currentBattingTeam = null;
  for (const t of tables) {
    const battingTeam = isBattingHeader(t);
    const headerCells = [...(t.querySelector('tr')?.children||[])].map(c=>clean(c.innerText));
    if (battingTeam) {
      currentBattingTeam = battingTeam;
      const rows = [...t.querySelectorAll('tr')].slice(1);
      for (const tr of rows) {
        const cells = [...tr.children].map(c=>clean(c.innerText));
        if (cells.length<6) continue;
        const [rawName, dismissal, R,B,fours,sixes,SR] = cells;
        const lower = rawName.toLowerCase();
        if (lower.startsWith('extras')||lower.startsWith('total')) continue;
        const name = dismissal ? rawName.replace(dismissal,'').trim() : rawName.trim();
        battingRows.push([matchId, currentBattingTeam, name, dismissal, R, B, fours, sixes, SR].map(csvEscape).join(','));
      }
    } else if (headerCells[0]==='Bowling') {
      // bowling table right after a batting innings is bowled by the OTHER team, not this one
      const bowlingTeam = teams.find(t=>t!==currentBattingTeam) || currentBattingTeam;
      const rows = [...t.querySelectorAll('tr')].slice(1);
      for (const tr of rows) {
        const cells = [...tr.children].map(c=>clean(c.innerText));
        const vals = cells[0]==='' ? cells.slice(1) : cells;
        if (vals.length<6) continue;
        const core = vals.slice(0,7); // bowler,O,M,Dot,R,W,Econ
        const [wides, noballs] = parseExtras(vals[7]);
        bowlingRows.push([matchId, bowlingTeam, ...core, wides, noballs].map(csvEscape).join(','));
      }
    }
  }
  return {battingRows, bowlingRows, blocked:false};
}
window.__fetchScorecard = fetchScorecard;
async function runBatch(ids, delayMs){
  let bat = [], bowl = [], blockedCount = 0;
  for (const id of ids) {
    const r = await window.__fetchScorecard(id);
    if (r.blocked) blockedCount++;
    bat.push(...r.battingRows);
    bowl.push(...r.bowlingRows);
    await new Promise(res=>setTimeout(res, delayMs));
  }
  window.__buf = bat.join('\n') + '\n===BOWLING===\n' + bowl.join('\n');
  return {batCount: bat.length, bowlCount: bowl.length, buflen: window.__buf.length, blockedCount};
}
window.__runBatch = runBatch;
```

Then loop through `window.__ids` in **batches of ~15-20 with a 1200ms delay**, one
`javascript_tool` call per batch, combining the fetch and the blob-download trigger in the same
call to save round trips:

```js
const batch = window.__ids.slice(START, START+20);
const r = await window.__runBatch(batch, 1200);
const blob = new Blob([window.__buf], {type:'text/csv'});
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url; a.download = `PREFIX_batch_${String(BATCHNUM).padStart(2,'0')}.csv`;
document.body.appendChild(a); a.click(); a.remove();
JSON.stringify(r);
```

Use `d1` as `PREFIX` for Division 1 and `wk` for Weekenders Cup — `combine_scorecards.py` (step
3) globs for `{prefix}_batch_*.csv`, so the prefix has to match exactly. Bowling rows now have 11
columns (`matchId,team,bowler,O,M,Dot,R,W,Econ,wides,noballs`) — `combine_scorecards.py`'s
`bowl_header` already matches this, no edit needed unless the site's table shape changes again.

Check `blockedCount` is 0 each time. If it's not, you've tripped Cloudflare — navigate back to
the `listMatches.do` URL, wait ~8-10s for the challenge to clear (check `document.title` isn't
"Just a moment..."), re-run the two `window.__ids`/`window.__fetchScorecard` setup blocks (page
reload wipes `window` state), and resume from where you left off.

After each batch, `mv ~/Downloads/PREFIX_batch_NN.csv NJSBCL/data/raw_scorecards/` (create that
directory if it doesn't exist — clear it out at the start of a fresh run first, don't mix old
and new batch files). Do this for both series (~15 batches each).

## Step 3 — Combine raw batches into the final scorecard CSVs

```
cd NJSBCL && source .venv/bin/activate  # or: python3 -m venv .venv && pip install pandas openpyxl
python3 combine_scorecards.py d1   # writes data/d1_scorecards_{batting,bowling}.csv
python3 combine_scorecards.py wk   # writes data/wk_scorecards_{batting,bowling}.csv
mv data/d1_scorecards_batting.csv data/division1_scorecards_batting.csv
mv data/d1_scorecards_bowling.csv data/division1_scorecards_bowling.csv
mv data/wk_scorecards_batting.csv data/weekenderscup_scorecards_batting.csv
mv data/wk_scorecards_bowling.csv data/weekenderscup_scorecards_bowling.csv
```

`build_data.py` (step 5) expects those `division1_`/`weekenderscup_`-prefixed names exactly —
don't skip the `mv`. The combine step prints unique matchId counts — sanity check against the
true-totals CSV row count. The
difference should be small (10-15 per series) and should be **abandoned matches only** (0/0,
no play) — spot check a couple of the "missing" matchIds by opening
`https://cricclubs.com/NJSBCL/viewScorecard.do?matchId=<id>&clubId=2690` if the gap looks larger
than that; something broke in the scrape if so, don't silently proceed.

## Step 4 — Schedule exports (for upcoming fixtures)

Navigate to `https://cricclubs.com/NJSBCL/fixtures.do?clubId=2690&league=<58|60>`, click the
green Excel export icon (top right of the table), move the downloaded `.xlsx` from
`~/Downloads` to `NJSBCL/data/division1_schedule.xlsx` / `weekenderscup_schedule.xlsx`.

## Step 4b — Points table (for standings + Elo win probability)

Navigate to `https://cricclubs.com/NJSBCL/viewLeaguePointstable.do?clubId=2690&league=<58|60>`
and wait ~4s. The groups' tables are plain `<table>` elements on the page — find them by
header text, not by fixed index (the index shifts between the two series/pages):

```js
function clean(s){return s.replace(/\s+/g,' ').trim();}
function csvEscape(s){ s=String(s??''); if(/[",\n]/.test(s)) return '"'+s.replace(/"/g,'""')+'"'; return s; }
const tables=[...document.querySelectorAll('table')];
const groupTables = tables
  .map((t,i)=>({i, header: (()=>{const hr=t.querySelector('tr'); return hr?[...hr.children].map(c=>clean(c.innerText)).join('|'):'';})()}))
  .filter(x=>/^#\|TEAM\|MAT/i.test(x.header));
// groupTables.length is 2 for Division 1 (Group A, B), 4 for Weekenders Cup (Group A-D), in order
const rows = [];
groupTables.forEach(({i}, gi) => {
  const groupLetter = String.fromCharCode(65+gi); // A, B, C, D
  const trs = [...tables[i].querySelectorAll('tr')].map(tr=>[...tr.children].map(c=>clean(c.innerText)))
    .filter(r=>r.length===12 && r[0]!=='#');  // real rows only — each has a hidden "Loading ..."
    // duplicate row right after it (mobile-responsive artifact, same pattern seen elsewhere
    // on this site), filtering to length===12 drops those automatically
  for (const r of trs) rows.push([groupLetter, ...r].map(csvEscape).join(','));
});
window.__points = rows;
'rows=' + rows.length;
```

Then download exactly as before:

```js
const header = 'group,rank,team,mat,won,lost,nr,tie,pts,winpct,netrr,for,against';
const csv = header + '\n' + window.__points.join('\n');
const blob = new Blob([csv], {type:'text/csv'});
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url; a.download = 'points_table.csv';
document.body.appendChild(a); a.click(); a.remove();
```

Move to `NJSBCL/data/division1_points_table.csv` / `weekenderscup_points_table.csv`. A handful of
`pts` values may have a trailing `*` (site footnote, usually a forfeit-penalty adjustment) —
`build_data.py` already strips it when parsing, no action needed here.

## Step 4c — Over-by-over data for our own bowlers (death-overs metric)

Powers the "Death overs (last 3)" dashboard section — who to trust with the ball in the closing
overs. Scoped to **our own bowling figures only** (Samudhra Gladiators / VRK Gladiators), not the
whole league — this is about who WE hand the ball to, not opponent scouting, so the match list is
small (~15 + ~13 matches) and cheap to redo every rescrape.

First get the matchId list for our own team (already-combined scorecards CSVs are the easiest
source, no new page needed):

```
cd NJSBCL && source .venv/bin/activate && python3 - <<'EOF'
import pandas as pd
d1 = pd.read_csv("data/division1_scorecards_batting.csv")
wk = pd.read_csv("data/weekenderscup_scorecards_batting.csv")
print(sorted(d1[d1["team"].str.strip() == "Samudhra Gladiators"]["matchId"].unique().tolist()))
print(sorted(wk[wk["team"].str.strip() == "VRK Gladiators"]["matchId"].unique().tolist()))
EOF
```

Each match's `viewScorecard.do` page has an "Over by Over Score" tab that links to a **separate
page** (`overbyoverscoreview.do`), not an in-page tab — clicking it navigates and can trip
Cloudflare's challenge on the first hit of a URL pattern never visited this session (wait ~6s,
same recovery as everywhere else in this doc). Once cleared, direct `fetch()` calls to that same
URL pattern work fine, same as the scorecard fetches in step 2.

The page has one `<table>` per innings titled `"<Team> Batting"`, with rows `#, Bowler, Runs,
Score` — one row per over, where the "Bowler" cell mixes the bowler's short name with that over's
ball-by-ball outcomes (e.g. `"Kishan P 6 0 0 0 0 1wd 0"`). We only want the table where the
*opponent* is batting (i.e. where OUR team was bowling) — the other team's name appears in the
title:

```js
function clean(s){ return s.replace(/\s+/g,' ').trim(); }
function csvEscape(s){ s=String(s??''); if(/[",\n]/.test(s)) return '"'+s.replace(/"/g,'""')+'"'; return s; }
async function fetchOverByOver(matchId, gladiatorsTeamName){
  const url = `https://cricclubs.com/NJSBCL/overbyoverscoreview.do?matchId=${matchId}&clubId=2690`;
  const res = await fetch(url);
  if (res.status !== 200) return {rows:[], blocked:true, status:res.status};
  const html = await res.text();
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const tables = [...doc.querySelectorAll('table')];
  const target = tables.find(t => {
    const h = clean(t.querySelector('tr')?.innerText || '');
    return /Batting$/.test(h) && !h.startsWith(gladiatorsTeamName);
  });
  if (!target) return {rows:[], blocked:false, missing:true};
  const trs = [...target.querySelectorAll('tr')].slice(2); // skip title row + header row
  const rows = [];
  for (const tr of trs) {
    const cells = [...tr.children].map(c=>clean(c.innerText));
    if (cells.length < 4) continue;
    const [overNum, bowlerCell, runs] = cells;
    if (!overNum || !/^\d+$/.test(overNum)) continue;
    const m = bowlerCell.match(/^(.*?)\s+((?:\d+(?:wd|nb)?|W)(?:\s+(?:\d+(?:wd|nb)?|W))*)$/i);
    const bowler = m ? m[1].trim() : bowlerCell;
    rows.push([matchId, overNum, bowler, runs].map(csvEscape).join(','));
  }
  return {rows, blocked:false};
}
window.__fetchOverByOver = fetchOverByOver;
async function runOversBatch(ids, gladiatorsTeamName, delayMs){
  let all = [], blockedCount = 0;
  for (const id of ids) {
    const r = await window.__fetchOverByOver(id, gladiatorsTeamName);
    if (r.blocked) blockedCount++;
    all.push(...r.rows);
    await new Promise(res=>setTimeout(res, delayMs));
  }
  window.__oversBuf = all.join('\n');
  return {rowCount: all.length, blockedCount};
}
window.__runOversBatch = runOversBatch;
```

Then one batch per series (small enough to do in one call each — 15 and 13 matches):

```js
const ids = [/* the matchId list from above */];
const r = await window.__runOversBatch(ids, 'Samudhra Gladiators', 1200); // or 'VRK Gladiators'
const blob = new Blob([window.__oversBuf], {type:'text/csv'});
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url; a.download = 'd1_gladiators_overs.csv'; // or wk_gladiators_overs.csv
document.body.appendChild(a); a.click(); a.remove();
JSON.stringify(r);
```

Move + rename with a header row prepended (no combine script needed, small enough to handle
directly):

```
mv ~/Downloads/d1_gladiators_overs.csv data/division1_gladiators_overs.csv
mv ~/Downloads/wk_gladiators_overs.csv data/weekenderscup_gladiators_overs.csv
# prepend "matchId,overNum,bowler,runs" as the header row to each file
```

`build_data.py`'s `load_death_overs()` reads these directly (skips gracefully with `None` if the
files don't exist, so this step is optional but should be kept current each rescrape) — it takes
the last 3 over-numbers of each match as the death overs and resolves bowler short names via the
same `abbrev_map` used elsewhere.

## Step 5 — Rebuild the dashboard

```
cd NJSBCL/dashboard && source ../.venv/bin/activate
python3 build_data.py
```

Spot-check the output against something you know is true — e.g. Samudhra Gladiators' win/loss
record should match the points table shown on the NJSBCL homepage (2026 Division 1 tab), or ask
Sandheep for a result he can eyeball. Then tell him it's done — he can just open
`NJSBCL/dashboard/index.html` (or refresh it if already open) to see the refreshed data.

## Notes

- `NJSBCL/data/raw_scorecards/` is scratch space for this skill — safe to delete and rebuild
  each run, not meant to be committed as final data.
- The season-aggregate leaderboard CSVs (`division1_batting_all_teams.csv` etc.) and the
  Gladiators-specific season-stat CSVs from earlier scrapes are **not** inputs to
  `build_data.py` — only the scorecards + true-totals + schedule + points-table files are.
  Don't bother refreshing those unless Sandheep specifically asks for the standalone
  leaderboards again.
- `build_data.py` also computes an Elo rating per team from the true-totals results (chess-style,
  starts everyone at 1500, updates chronologically by matchId order) and uses it for the
  dashboard's win-probability display — no separate scrape needed for that, it falls out of data
  you already collected in steps 1-2.
- `build_data.py` also computes a "bowlers to target" weakness ranking per opponent team, from the
  wides/noballs columns collected in step 2 — no separate scrape needed. It z-scores economy,
  worst single-match economy, and extras rate across the whole league's bowlers (min 8 overs
  bowled to qualify) and surfaces each team's 3 weakest. Rendered in the dashboard's "Bowling
  battle" section, alongside a mirrored "bowling strengths" ranking (low economy + high dot-ball
  rate) for our own bowlers, from the same scorecard data.
- `build_data.py` also computes a "death overs (last 3)" ranking for our own bowlers from the
  dedicated over-by-over scrape in step 4c — see that step for the scrape itself.
- `build_data.py` also computes a **home/away win-rate split** per team, purely derived from data
  already scraped in earlier steps — no new scrape needed. It works despite the schedule's
  `Ground` field not being a real venue (see the venue-data TODO below): `Ground` reliably names
  whichever of the two teams is hosting, so `attach_venue()` matches each completed match (by
  matchId) to its schedule row — pairing them by team-pair + chronological order, since the two
  tables don't share an ID — and reads the host straight off `Ground`. Verified 2026-08-12: 288/288
  Division 1 matches matched, 276/283 Weekenders Cup (the 7 misses were all genuine `Ground=TBD`
  rows, not matching errors), and home+away win counts summed exactly to each team's total wins
  for every spot-checked team. Rendered as a "Home / away record" tile in the season-record grid.
- `build_data.py` also computes a **batting collapse rate** per team, purely from the batting
  scorecard CSV already scraped in step 2 — no new scrape needed (`detect_collapses()`). Defined
  as: 3+ of the top 7 batsmen (scorecard row order = batting order) dismissed for a combined 20
  runs or fewer, anywhere in the innings. The top-7 restriction is load-bearing, not cosmetic —
  verified 2026-08-12 that without it, the metric mostly flags the last few batters going cheap at
  the end of an innings (normal in this format; median innings here runs ~10 batters), which made
  even the league's strongest team (13-2 record) show a 73% "collapse" rate on an obviously bogus
  worst-case (tail folding *after* the top order had already set up 92 runs). Restricting to top 7
  and spot-checking the flagged "worst" instances confirmed they're genuine early-innings
  disasters (e.g. 4 wickets for 4 runs right after the one big partnership). Rendered as a
  "Batting collapses" section (par-target-row style) showing collapse % + worst instance, both
  teams, right before "Top 3 batsmen".
- There's a second page, `charts.html` (+ `charts.js`), added 2026-08-12 — Gladiators-only
  season charts, not opponent-specific. All derived from data already in `data.js` under each
  series' `gladiatorsCharts` key: no new scraping needed for it, just keep running
  `build_data.py` as normal and it regenerates alongside everything else. Contents: a suggested
  best playing XI (`best_playing_xi()` — batting value = average+strike rate, bowling value =
  economy+dot%, both z-scored against the *whole league* via `batter_strength_pool()` /
  `bowler_strength_pool()`, not just our own squad; keeper identified from the scorecard's `†`
  marker), an Elo rating trajectory chart (`compute_elo(results, track_team=...)` now optionally
  returns a match-by-match history alongside the final ratings), and full squad batting/bowling
  leaderboards (every player who's played for us, not just the top 3 shown on the main page).
- The Best XI is **interactive** (added 2026-08-12): `data.js` exposes the full candidate roster
  (`gladiatorsCharts.bestXI.roster`), not just the picked 11. `build_data.py`'s selection logic
  was split into `build_squad_roster()` (data prep) and a pure `select_xi(roster)` (no pandas,
  just dict/list logic) specifically so it could be ported 1:1 to JS — `charts.js`'s `selectXI()`
  is a line-by-line mirror of it. Clicking a player chip toggles them into `state.unavailable` and
  both functions re-run client-side against the filtered roster — no rebuild, no server
  round-trip. If you change the Python selection algorithm, update the JS copy to match or the
  two will silently diverge.
- `build_squad_roster()` deliberately includes **every** player who's appeared for the team this
  season (any batting innings or bowling over at all), not just those clearing
  `batter_strength_pool`/`bowler_strength_pool`'s qualifying thresholds — Sandheep flagged
  (2026-08-12) that fringe players were silently missing from the availability-toggle list.
  Unqualified players keep `battingScore`/`bowlingScore` as `null` (a 1-2 innings sample isn't a
  reliable ranking signal) but still appear as real roster entries, so they're available as an
  emergency fallback if enough regulars are marked unavailable. Caught a real bug fixing this:
  `select_xi()`'s "fill remaining spots" step originally treated a missing score as `0`, which
  made completely unproven players rank *above* proven regulars with a merely below-average score
  (a real -0.31 outranks nothing, but "nothing" was being read as neutral). Fixed by giving
  zero-score players `-Infinity` in that comparison instead — they now only get picked once every
  actually-scored option is exhausted. Both `select_xi()` and `selectXI()` were updated together.

## TODO for a future rescrape — toss data (not yet implemented)

Sandheep wants a toss-advice upgrade: right now the dashboard's toss recommendation is *inferred*
from each team's bat-first-vs-chasing win-rate split (a proxy). The better version uses the
**actual** toss result — who won the toss and what they chose — so the dashboard can check
whether teams that won the toss and picked bat/bowl actually converted that into wins, a more
direct signal than the current proxy. This was explicitly deferred (2026-08-11) — do NOT
implement the analysis/UI for it without Sandheep asking, but DO capture the raw data next time
this skill runs, so it's ready when he does:

- Check `viewScorecard.do?matchId=...` (Step 2) and/or the `Info` tab on that same page for toss
  wording — it wasn't found in the main scorecard tables during the 2026-08-11 rescrape (no
  "toss" text on the page body), so the "Info" tab (a separate in-page or linked tab, similar to
  "Over by Over Score") is the next place to check. If it's genuinely not exposed anywhere on
  cricclubs for this league, tell Sandheep rather than guessing/fabricating toss outcomes.
- If found, capture per match: which team won the toss, and whether they chose to bat or bowl.
  Store as e.g. `data/division1_toss.csv` / `data/weekenderscup_toss.csv` with columns
  `matchId,tossWinner,tossDecision`, following the same blob-download pattern as everything else
  in this doc.

## TODO for a future rescrape — real match venue / ground (not yet implemented)

Sandheep wants actual physical match locations (not just "hosted by Team X"). Investigated
2026-08-12, deferred at his request — he's looking for a more reliable source himself, so don't
resume this without him asking. Findings so far, to avoid re-deriving them from scratch:

- The schedule export's `Ground` column (used today for fixture-card venues) is **not** a real
  location — cross-checked all 400 Division 1 + all 800 Weekenders Cup 2026 matches and every
  single `Ground` value is just the hosting team's own name, not a park/address.
- `viewTeams.do?league=<id>&year=2026&clubId=2690` (Team List page) DOES have a real `Home
  Ground` column per team (e.g. "Daniel P. Ryan Field," "Cedarbrook Park") matching the site's
  genuine grounds directory (`viewGrounds.do?clubId=2690`, has street addresses). This is
  team-level, not match-level — no per-match venue was found anywhere (checked scorecard "Info"
  tab too, nothing there).
- Coverage is incomplete: 9/40 Division 1 teams and 44/80 Weekenders Cup teams have a blank
  `Home Ground`. League IDs found: Division 1 `league=58`, Division 2 `league=59`, Weekenders Cup
  `league=60`, T-20 Championship `league=61` (2026 for all). Cross-referencing a team missing its
  ground in one league against the other three 2026 leagues did NOT reliably fill gaps — no exact
  name matches at all, and fuzzy substring matches were mostly false positives (generic names like
  "Warriors" collided across unrelated teams). Didn't find the 2025 Division 1 league ID (its
  nav link is inside a hover-triggered dropdown that didn't yield an href through the usual
  extraction) — worth trying if picking this back up, but no reason to expect it fixes the
  team-vs-match granularity problem even if found.
- Bottom line if resumed: `viewTeams.do`'s `Home Ground` is real but only gets you "which park a
  team calls home," not "where this specific match on this specific date was played" (teams could
  plausibly play away matches at the opponent's ground, or a neutral one) — that distinction
  matters if Sandheep wants per-match accuracy rather than a per-team approximation.
