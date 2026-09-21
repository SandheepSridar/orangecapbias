/* NJSBCL Scout — knockout bracket (reads the same NJSBCL_DATA as app.js/standings.js). */
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
function fmtRR(rr) { return (rr >= 0 ? "+" : "") + rr.toFixed(2); }
function ord(n) {
  const s = ["th", "st", "nd", "rd"], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

/* ── Controls ──────────────────────────────────────────────────────── */
function buildSeriesPills() {
  const box = $("series-pills");
  box.innerHTML = "";
  SERIES_KEYS.forEach((key) => {
    const b = el("button", "pill", NJSBCL_DATA.series[key].label);
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

function renderDataUpdated() {
  const d = new Date(NJSBCL_DATA.generated + "T00:00:00");
  $("data-updated-badge").textContent =
    "Data last updated: " + d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

/* ── Our tie ───────────────────────────────────────────────────────── */
function scoutLine(them) {
  /* One line each on their danger man, their best bowler and the toss — the three things
     worth knowing before you've opened the full scouting page. */
  const bits = [];
  const bat = them.topBatsmen && them.topBatsmen[0];
  const bowl = them.topBowlers && them.topBowlers[0];
  if (bat) bits.push(`<b>${bat.player}</b> is their run-scorer — ${bat.runs} runs at a strike rate of ${bat.sr}.`);
  if (bowl) bits.push(`<b>${bowl.player}</b> leads their attack with ${bowl.wickets} wickets at ${bowl.econ} an over.`);
  if (them.toss && them.toss.recommendation) {
    bits.push(`If we win the toss, <b>${them.toss.recommendation} first</b> — ${them.toss.reason}`);
  }
  if (them.parTarget && them.parTarget.targetToChase && them.parTarget.targetToChase.value != null) {
    bits.push(`Chasing them, <b>${them.parTarget.targetToChase.value}</b> has been the number to beat.`);
  }
  return bits;
}

function renderOurTie() {
  const s = currentSeriesData();
  const box = $("our-tie-content");
  box.innerHTML = "";
  const ko = s.knockouts;

  if (!ko) {
    box.appendChild(el("div", "empty-note", "No knockout bracket configured for this series."));
    return;
  }
  if (!ko.us) {
    box.appendChild(el("div", "empty-note",
      `${s.gladiators} did not finish in the top ${ko.qualifiersPerGroup} of their group, so there's no knockout tie to scout.`));
    return;
  }

  const u = ko.us;
  const them = s.teams[u.opponent];
  const card = el("div", "ko-hero");

  const head = el("div", "ko-hero-head");
  head.appendChild(el("div", "ko-hero-side",
    `<span class="ko-seed us">${u.group}${u.seed}</span>
     <span class="ko-hero-team us">${s.gladiators}</span>`));
  head.appendChild(el("div", "ko-hero-vs", "vs"));
  head.appendChild(el("div", "ko-hero-side right",
    `<span class="ko-hero-team">${u.opponent}</span>
     <span class="ko-seed">${u.group}${u.opponentSeed}</span>`));
  card.appendChild(head);

  card.appendChild(el("div", "ko-hero-sub",
    `Pre-quarter final &middot; ${ord(u.seed)} vs ${ord(u.opponentSeed)} in Group ${u.group}`));

  if (u.winProb != null) {
    const pct = Math.round(u.winProb);
    const bar = el("div", "ko-prob");
    bar.appendChild(el("div", "ko-prob-bar",
      `<span class="ko-prob-fill" style="width:${pct}%"></span>`));
    bar.appendChild(el("div", "ko-prob-label",
      `<b>${pct}%</b> win probability &middot; Elo ${u.ourElo} vs ${u.theirElo}`));
    card.appendChild(bar);
  }

  if (them) {
    const ul = el("ul", "ko-scout");
    scoutLine(them).forEach((b) => ul.appendChild(el("li", null, b)));
    if (ul.children.length) card.appendChild(ul);
    card.appendChild(el("a", "ko-cta",
      `Full scouting report on ${u.opponent} →`));
    card.lastChild.href = `index.html?series=${encodeURIComponent(state.series)}&opponent=${encodeURIComponent(u.opponent)}`;
  }
  box.appendChild(card);
}

/* ── Draw ──────────────────────────────────────────────────────────── */
function tieRow(t, gladiators) {
  const row = el("div", "ko-tie" + (t.isOurs ? " ours" : ""));
  row.appendChild(el("span", "ko-seed" + (t.high.isUs ? " us" : ""), `${t.group}${t.high.seed}`));
  row.appendChild(el("span", "ko-tie-team" + (t.high.isUs ? " us" : ""), t.high.team));
  row.appendChild(el("span", "ko-tie-vs", "v"));
  row.appendChild(el("span", "ko-tie-team right" + (t.low.isUs ? " us" : ""), t.low.team));
  row.appendChild(el("span", "ko-seed" + (t.low.isUs ? " us" : ""), `${t.group}${t.low.seed}`));
  row.appendChild(el("span", "ko-tie-prob",
    t.highWinProb != null ? `${Math.round(t.highWinProb)}%` : "—"));
  return row;
}

function renderDraw() {
  const s = currentSeriesData();
  const box = $("draw-content");
  box.innerHTML = "";
  const ko = s.knockouts;
  if (!ko) { box.appendChild(el("div", "empty-note", "No bracket for this series.")); return; }

  box.appendChild(el("div", "ko-callout",
    `<b>The league hasn't published the knockout schedule yet.</b> Our own tie is confirmed
     ${ko.us ? `(${s.gladiators} drew ${ko.us.opponent})` : ""}; the other seven follow the standard
     1v8 seeding and will be corrected here once cricclubs posts the fixtures. Rule 7 defers the
     format to "the schedule published", so nothing below the pre-quarters is guessed at.`));

  const legend = el("div", "ko-legend");
  legend.innerHTML = `<span>Percentage is the higher seed's Elo win probability.</span>`;
  box.appendChild(legend);

  ko.groups.forEach((g) => {
    const wrap = el("div", "standings-group-wrap");
    wrap.appendChild(el("h3", null, `Group ${g.group}`));
    ko.preQuarters.filter((t) => t.group === g.group)
      .forEach((t) => wrap.appendChild(tieRow(t, s.gladiators)));
    box.appendChild(wrap);
  });
}

/* ── Qualified ─────────────────────────────────────────────────────── */
function qualifiedTable(gladiators, g) {
  const wrap = el("div", "standings-table-wrap");
  const table = document.createElement("table");
  table.className = "standings-table";
  const thead = el("thead");
  const headRow = el("tr");
  ["Seed", "Team", "W", "L", "Pts", "NetRR", "Elo"].forEach((h) => headRow.appendChild(el("th", null, h)));
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = el("tbody");
  g.qualified.forEach((q) => {
    const row = el("tr");
    if (q.isUs) row.classList.add("gladiators-row");
    row.appendChild(el("td", null, String(q.seed)));
    row.appendChild(el("td", "team-name", q.team));
    row.appendChild(el("td", null, String(q.won)));
    row.appendChild(el("td", null, String(q.lost)));
    row.appendChild(el("td", "pts", q.pts != null ? String(q.pts) : "—"));
    row.appendChild(el("td", null, fmtRR(q.netRR)));
    row.appendChild(el("td", null, q.elo != null ? String(q.elo) : "—"));
    tbody.appendChild(row);
  });

  if (g.cutLine) {
    const row = el("tr", "ko-cut-row");
    row.appendChild(el("td", null, "9"));
    row.appendChild(el("td", "team-name", `${g.cutLine.team} <span class="ko-cut-tag">missed out</span>`));
    row.appendChild(el("td", null, ""));
    row.appendChild(el("td", null, ""));
    row.appendChild(el("td", "pts", g.cutLine.pts != null ? String(g.cutLine.pts) : "—"));
    row.appendChild(el("td", null, fmtRR(g.cutLine.netRR)));
    row.appendChild(el("td", null, ""));
    tbody.appendChild(row);
  }
  table.appendChild(tbody);
  wrap.appendChild(table);
  return wrap;
}

function renderQualified() {
  const s = currentSeriesData();
  const box = $("qualified-content");
  box.innerHTML = "";
  const ko = s.knockouts;
  if (!ko) { box.appendChild(el("div", "empty-note", "No bracket for this series.")); return; }

  ko.groups.forEach((g) => {
    const wrap = el("div", "standings-group-wrap");
    wrap.appendChild(el("h3", null, `Group ${g.group}`));
    wrap.appendChild(qualifiedTable(s.gladiators, g));
    if (g.cutLine && g.cutLine.ptsBehind != null) {
      wrap.appendChild(el("div", "doc-note",
        `${g.cutLine.team} finished ${g.cutLine.ptsBehind} point${g.cutLine.ptsBehind === 1 ? "" : "s"} outside the cut.`));
    }
    box.appendChild(wrap);
  });
}

/* ── Wiring ────────────────────────────────────────────────────────── */
function renderAll() {
  renderOurTie();
  renderDraw();
  renderQualified();
}

renderDataUpdated();
buildSeriesPills();
renderAll();
