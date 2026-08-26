/* NJSBCL Scout — league standings (reads the same NJSBCL_DATA as app.js/charts.js/recap.js). */
"use strict";

const $ = (id) => document.getElementById(id);
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
};

const SERIES_KEYS = Object.keys(NJSBCL_DATA.series);
const state = { series: SERIES_KEYS[0] };

function currentSeriesData() { return NJSBCL_DATA.series[state.series]; }

/* ── Controls ──────────────────────────────────────────────────────── */
function buildSeriesPills() {
  const box = $("series-pills");
  box.innerHTML = "";
  SERIES_KEYS.forEach((key) => {
    const label = NJSBCL_DATA.series[key].label;
    const b = el("button", "pill", label);
    if (key === state.series) b.classList.add("active");
    b.addEventListener("click", () => {
      if (state.series === key) return;
      state.series = key;
      box.querySelectorAll(".pill").forEach((p) => p.classList.remove("active"));
      b.classList.add("active");
      renderAll();
    });
    box.appendChild(b);
  });
}

/* ── Data freshness ───────────────────────────────────────────────── */
function renderDataUpdated() {
  const d = new Date(NJSBCL_DATA.generated + "T00:00:00");
  const formatted = d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  $("data-updated-badge").textContent = `Data last updated: ${formatted}`;
}

/* ── Path to #1 ────────────────────────────────────────────────────── */
function fmtRR(rr) { return rr >= 0 ? `+${rr.toFixed(2)}` : rr.toFixed(2); }
function plural(n, word) { return `${n} ${word}${n === 1 ? "" : "s"}`; }

function scenarioCard(title, bigText, note) {
  const card = el("div", "metric-tile");
  card.innerHTML = `<h3>${title}</h3>
    <div style="font-size:1.6rem;font-weight:800;font-family:'Sora',sans-serif;">${bigText}</div>
    <div class="mt-note">${note}</div>`;
  return card;
}

/* One row of the checklist. `runningPts` shown on the right for our own matches (a win
   moves the total forward by 4); omitted for a rival's fixture, since we don't control
   or know their outcome — those rows just flag "this one's worth watching." */
function scenarioStep(num, title, date, runningPts) {
  const watch = runningPts == null;
  const step = el("div", `scenario-step${watch ? " watch" : ""}`);
  const running = watch ? "" : `<div class="scenario-step-running"><span class="num">${runningPts}</span><span class="lbl">pts</span></div>`;
  step.innerHTML = `<div class="scenario-step-num">${num}</div>
    <div class="scenario-step-body">
      <div class="scenario-step-title">${title}</div>
      <div class="scenario-step-date">${date}</div>
    </div>
    ${running}`;
  return step;
}

function ourChecklist(sc, heading) {
  const wrap = el("div", "scenario-block");
  wrap.appendChild(el("h3", null, heading));
  const steps = el("div", "scenario-steps");
  let running = sc.pts;
  sc.fixtures.forEach((f, i) => {
    running += 4;
    steps.appendChild(scenarioStep(i + 1, `Beat ${f.opponent}`, f.date, running));
  });
  wrap.appendChild(steps);
  return wrap;
}

function rivalWatchlist(rival) {
  const wrap = el("div", "scenario-block");
  wrap.appendChild(el("h3", null, `Meanwhile, keep an eye on ${rival.team}`));
  wrap.appendChild(el("p", "doc-note",
    `Their remaining fixtures — any loss or tie here works in our favor, independent of what we do.`));
  const steps = el("div", "scenario-steps");
  rival.fixtures.forEach((f, i) => {
    steps.appendChild(scenarioStep(i + 1, `${rival.team} vs ${f.opponent}`, f.date, null));
  });
  wrap.appendChild(steps);
  return wrap;
}

function renderScenario() {
  const s = currentSeriesData();
  const box = $("scenario-content");
  box.innerHTML = "";
  const sc = s.promotionScenario;
  if (!sc) {
    box.appendChild(el("div", "empty-note", "No standings scenario available for this series yet."));
    return;
  }

  const grid = el("div", "metric-grid");
  grid.appendChild(scenarioCard(
    "Current position",
    `#${sc.rank} of ${sc.rankOf}`,
    `Group ${sc.group} &middot; ${plural(sc.pts, "pt")} &middot; NetRR ${fmtRR(sc.netRR)} &middot; ${plural(sc.remaining, "game")} left`,
  ));
  grid.appendChild(scenarioCard(
    "If we win out",
    `${sc.ceiling} pts`,
    `Base case: 4 pts per win, no bonus points assumed — those need a big win margin that can't be
     predicted ahead of a match.`,
  ));
  box.appendChild(grid);

  if (sc.fixtures.length) {
    box.appendChild(ourChecklist(sc, sc.alreadyFirst ? "Stay unbeaten to hold the top spot" : "What we need to do"));
  }

  if (sc.alreadyFirst) {
    box.appendChild(el("div", "scenario-verdict",
      `${s.gladiators} are already top of Group ${sc.group}. Win out and no rival can catch up on
       points alone — the job is to not let anyone's own ceiling pass ${sc.ceiling}.`));
  } else {
    const L = sc.leader;
    if (sc.tiedOnPointsWithLeader) {
      box.appendChild(el("div", "scenario-verdict",
        `Tied on points with ${L.team} right now (${L.pts} each) — they lead on NetRR
         (${fmtRR(L.netRR)} vs our ${fmtRR(sc.netRR)}), the actual tiebreaker for #1 today. Winning out
         keeps us level on points at best; closing that NetRR gap (or ${L.team} slipping in points)
         is what actually gets us to #1.`));
    } else if (L.clinchable) {
      box.appendChild(el("div", "scenario-verdict",
        `Win out and we finish with more points than ${L.team} can possibly reach — their ceiling is
         ${L.ceiling}, ours is ${sc.ceiling}. #1 is fully in our hands, no help needed.`));
    } else {
      box.appendChild(el("div", "scenario-verdict",
        `Win out and we reach ${sc.ceiling} — but ${L.team}'s own ceiling is ${L.ceiling} if they also
         win out, so that alone doesn't guarantee #1. They'd need to drop at least
         ${plural(L.ceiling - sc.ceiling, "point")} below their own ceiling too.`));
    }
    if (L.fixtures.length) box.appendChild(rivalWatchlist(L));
  }

  if (sc.above) {
    const A = sc.above;
    box.appendChild(el("div", "scenario-verdict",
      A.clinchable
        ? `Separately: win out and we finish above ${A.team} regardless of their results — their
           ceiling is ${A.ceiling}, ours is ${sc.ceiling}.`
        : `Separately, to leapfrog ${A.team} (currently ${plural(A.gapNow, "pt")} ahead): their own
           ceiling is ${A.ceiling} if they also win out, so winning out alone isn't a guarantee there
           either.`));
    if (A.fixtures.length) box.appendChild(rivalWatchlist(A));
  }

  box.appendChild(el("p", "doc-note",
    `Base case only: every remaining win is assumed worth 4 points, and the rule book's +1 bonus
     point (winning by 1.25&times; the loser's run rate or better) isn't baked in, since it can't be
     predicted ahead of a match.`));
}

/* ── Standings ─────────────────────────────────────────────────────── */
function standingsTable(gladiators, rows) {
  const wrap = el("div", "standings-table-wrap");
  const table = document.createElement("table");
  table.className = "standings-table";
  const thead = el("thead");
  const headRow = el("tr");
  ["#", "Team", "Mat", "W", "L", "T", "NR", "Pts", "Win%", "NetRR"].forEach((h) => headRow.appendChild(el("th", null, h)));
  thead.appendChild(headRow);
  table.appendChild(thead);
  const tbody = el("tbody");
  rows.forEach((r) => {
    const row = el("tr");
    if (r.team === gladiators) row.classList.add("gladiators-row");
    row.appendChild(el("td", null, String(r.rank)));
    row.appendChild(el("td", "team-name", r.team));
    row.appendChild(el("td", null, String(r.mat)));
    row.appendChild(el("td", null, String(r.won)));
    row.appendChild(el("td", null, String(r.lost)));
    row.appendChild(el("td", null, String(r.tie)));
    row.appendChild(el("td", null, String(r.nr)));
    row.appendChild(el("td", "pts", r.pts != null ? String(r.pts) : "—"));
    row.appendChild(el("td", null, `${r.winPct}%`));
    row.appendChild(el("td", null, r.netRR >= 0 ? `+${r.netRR.toFixed(2)}` : r.netRR.toFixed(2)));
    tbody.appendChild(row);
  });
  table.appendChild(tbody);
  wrap.appendChild(table);
  return wrap;
}

function renderStandings() {
  const s = currentSeriesData();
  const box = $("standings-content");
  box.innerHTML = "";
  const groups = s.standingsTable;
  if (!groups || !groups.length) {
    box.appendChild(el("div", "empty-note", "No standings scraped yet for this series."));
    return;
  }
  groups.forEach((g) => {
    const wrap = el("div", "standings-group-wrap");
    wrap.appendChild(el("h3", null, `Group ${g.group}`));
    wrap.appendChild(standingsTable(s.gladiators, g.rows));
    box.appendChild(wrap);
  });
}

/* ── Wiring ────────────────────────────────────────────────────────── */
function renderAll() {
  renderScenario();
  renderStandings();
}

renderDataUpdated();
buildSeriesPills();
renderAll();
