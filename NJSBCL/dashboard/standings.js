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

/* ── Scenario tree ─────────────────────────────────────────────────── */
function fmtRR(rr) { return (rr >= 0 ? "+" : "") + rr.toFixed(2); }

const OUTCOME_LABEL = { W: "Beat", L: "Lose to", NR: "No result vs" };

function scenarioRow(node, gladiators) {
  const row = el("div", "scenario-row" + (node.depth === 0 ? " root" : "") + (node.leaf ? " leaf" : ""));
  row.style.setProperty("--depth", node.depth);

  const cls = node.depth === 0 ? "now" : node.outcome.toLowerCase();
  const label = node.depth === 0 ? "NOW" : node.outcome;
  row.appendChild(el("span", `scenario-badge ${cls}`, label));

  const opp = node.depth === 0
    ? `${gladiators} as it stands`
    : `${OUTCOME_LABEL[node.outcome]} ${node.opponent}<span class="d">${node.date}</span>`;
  row.appendChild(el("span", "scenario-opp", opp));

  const nums = el("div", "scenario-nums");
  nums.appendChild(el("span", "scenario-num", `${node.pts}<span class="lbl">pts</span>`));
  nums.appendChild(el("span", "scenario-num nrr", `${fmtRR(node.nrr)}<span class="lbl">nrr</span>`));
  if (node.leaf) {
    const v = node.top1Guaranteed ? ["yes", "#1 clinched"]
      : node.top1Possible ? ["maybe", "#1 possible"]
        : ["no", `${node.bestRank}${node.bestRank === 2 ? "nd" : node.bestRank === 3 ? "rd" : "th"} at best`];
    nums.appendChild(el("span", `scenario-verdict ${v[0]}`, v[1]));
  }
  row.appendChild(nums);
  return row;
}

function scenarioDetail(node) {
  const d = el("div", "scenario-detail");
  d.style.setProperty("--depth", node.depth);
  const rankTxt = node.bestRank === node.worstRank
    ? `Finishes ${node.bestRank}${node.bestRank === 1 ? "st" : node.bestRank === 2 ? "nd" : node.bestRank === 3 ? "rd" : "th"} regardless of other results.`
    : `Finishes anywhere from ${node.bestRank}${node.bestRank === 1 ? "st" : "th"} to ${node.worstRank}${node.worstRank === 2 ? "nd" : node.worstRank === 3 ? "rd" : "th"}, depending on rivals.`;
  if (!node.blockers.length) {
    d.innerHTML = `${rankTxt} No rival can reach ${node.pts} points, so top spot is secure on this path.`;
    return d;
  }
  d.innerHTML = `${rankTxt} For #1 on this path, all of the following must hold:`;
  const ul = document.createElement("ul");
  node.blockers.forEach((b) => ul.appendChild(el("li", null, b.condition)));
  d.appendChild(ul);
  return d;
}

function renderScenarioTree() {
  const s = currentSeriesData();
  const box = $("scenario-content");
  box.innerHTML = "";
  const st = s.scenarioTree;
  if (!st) {
    box.appendChild(el("div", "empty-note",
      "No remaining fixtures — the season's group stage is complete for this team."));
    return;
  }

  // Honest framing up front: our own NRR is not the lever here, and saying so plainly
  // matters more than making the chart look winnable.
  const reach = st.contenders.filter((c) => c.minNrr > 0);
  const leader = st.contenders[0];
  if (leader) {
    box.appendChild(el("div", "scenario-callout",
      `<b>Read this first.</b> ${st.us} sit on ${st.base.pts} pts / ${fmtRR(st.base.nrr)} NRR.
       Net run rate is a season-long average, so three matches barely move it — every path below
       lands between ${fmtRR(Math.min(...leafNrrs(st)))} and ${fmtRR(Math.max(...leafNrrs(st)))}.
       ${leader.team} stay above ${fmtRR(leader.minNrr)} in every one of their own scenarios, so
       <b>#1 is won by rivals dropping points, not by our run rate</b>.`));
  }

  box.appendChild(el("p", "doc-note",
    `Projected scorelines: ` + st.projections.map((p) =>
      `<b>${p.opponent}</b> ${p.win.toFixed(0)}&ndash;${p.lose.toFixed(0)}` +
      (p.bonus ? ` (win = ${p.winPts} pts, clears the bonus margin)` : ` (win = ${p.winPts} pts)`)
    ).join(" &middot; ") +
    `. A no-result is worth 2 points and is excluded from NRR entirely, so those branches move
     points without touching run rate.`));

  const legend = el("div", "scenario-legend");
  legend.innerHTML = `
    <span><span class="scenario-badge w">W</span>win</span>
    <span><span class="scenario-badge l">L</span>loss</span>
    <span><span class="scenario-badge nr">NR</span>no result</span>
    <span>Tap any final row for what else has to happen.</span>`;
  box.appendChild(legend);

  const tree = el("div", "scenario-tree");
  (function walk(node) {
    const row = scenarioRow(node, st.us);
    tree.appendChild(row);
    if (node.leaf) {
      const detail = scenarioDetail(node);
      detail.hidden = true;
      tree.appendChild(detail);
      row.addEventListener("click", () => { detail.hidden = !detail.hidden; });
    }
    (node.children || []).forEach(walk);
  })(st.root);
  box.appendChild(tree);
}

function leafNrrs(st) {
  const out = [];
  (function walk(n) { if (n.leaf) out.push(n.nrr); (n.children || []).forEach(walk); })(st.root);
  return out;
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
  renderScenarioTree();
  renderStandings();
}

renderDataUpdated();
buildSeriesPills();
renderAll();
