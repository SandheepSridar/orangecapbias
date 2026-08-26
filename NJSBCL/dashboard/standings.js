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
    `Winning all ${sc.remaining} remaining match${sc.remaining === 1 ? "" : "es"} (4 pts each, base case —
     doesn't count any bonus point for a big-margin win) takes us to ${sc.ceiling} points.`,
  ));

  if (sc.alreadyFirst) {
    grid.appendChild(scenarioCard(
      "Defending #1",
      "Already there",
      `${s.gladiators} sit top of Group ${sc.group} right now. Stay ahead by not letting a rival's
       ceiling (their points + 4&times;their remaining games) pass ours.`,
    ));
  } else {
    const L = sc.leader;
    let bigText, note;
    if (sc.tiedOnPointsWithLeader) {
      bigText = "Tied — NetRR decides";
      note = `Tied on points with ${L.team} right now (${L.pts} each), but ${L.team} leads on NetRR
        (${fmtRR(L.netRR)} vs our ${fmtRR(sc.netRR)}) — that's the tiebreaker deciding #1 today. Both
        sides have ${plural(sc.remaining, "game")} left, so expect this to stay close.`;
    } else if (L.clinchable) {
      bigText = "In our hands";
      note = `Win out and we finish with more points than ${L.team} can possibly reach — their ceiling
        is ${L.ceiling}, ours is ${sc.ceiling}. #1 doesn't depend on their results.`;
    } else {
      bigText = `${plural(L.gapNow, "pt")} behind`;
      note = `Win out and we reach ${sc.ceiling} points — but ${L.team}'s own ceiling is ${L.ceiling} if
        they also win out, so winning out alone doesn't guarantee #1. They'd need to drop at least
        ${plural(L.ceiling - sc.ceiling, "point")} below their own ceiling too.`;
    }
    grid.appendChild(scenarioCard(`Path to overtake ${L.team}`, bigText, note));
  }

  if (sc.above) {
    const A = sc.above;
    grid.appendChild(scenarioCard(
      `Leapfrog ${A.team}`,
      A.clinchable ? "In our hands" : `${plural(A.gapNow, "pt")} behind`,
      A.clinchable
        ? `Win out and we finish above them regardless of their results — their ceiling is ${A.ceiling},
           ours is ${sc.ceiling}.`
        : `They have ${plural(A.remaining, "game")} left too (ceiling ${A.ceiling}) — winning out alone
           isn't a guarantee.`,
    ));
  }

  box.appendChild(grid);
  box.appendChild(el("p", "doc-note",
    `Base case only: every remaining win is assumed worth 4 points, and the rule book's +1 bonus
     point (winning by 1.25&times; the loser's run rate or better) isn't baked in, since it can't be
     predicted ahead of a match. "Remaining games" assumes the group finishes in lockstep, same as
     it has all season.`));
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
