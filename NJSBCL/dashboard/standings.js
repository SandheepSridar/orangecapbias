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
  renderStandings();
}

renderDataUpdated();
buildSeriesPills();
renderAll();
