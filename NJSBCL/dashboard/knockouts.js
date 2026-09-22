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
     <span class="ko-seed">${u.opponentGroup}${u.opponentSeed}</span>`));
  card.appendChild(head);

  const roundLabel = (ko.bracket.rounds.find((r) => r.key === u.round) || {}).label || "Knockout";
  card.appendChild(el("div", "ko-hero-sub",
    `${roundLabel} &middot; ${u.matchId} &middot; ${fmtMatchDate(u.date)} &middot; ` +
    `${ord(u.seed)} in Group ${u.group} vs ${ord(u.opponentSeed)} in Group ${u.opponentGroup}`));

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

/* ── Bracket ───────────────────────────────────────────────────────── */
/* The published bracket, played forward. Clicking a team sends it into the next round's
   slot; anything downstream that depended on the old result is cleared rather than left
   stale. Nothing is pre-filled — an Elo projection sitting there on load reads as a
   prediction, and what this page is for is the real draw. */

const SVG_NS = "http://www.w3.org/2000/svg";
const bracket = { winners: {}, elo: {}, seed: {}, consumer: {}, byId: {} };

function bracketData() {
  const ko = currentSeriesData().knockouts;
  return ko && ko.bracket ? ko.bracket : null;
}

function indexBracket() {
  Object.assign(bracket, { winners: {}, elo: {}, seed: {}, consumer: {}, byId: {} });
  const b = bracketData();
  if (!b) return;
  b.matches.forEach((m) => {
    bracket.byId[m.id] = m;
    ["a", "b"].forEach((side) => {
      const s = m[side];
      if (s.team) {
        bracket.seed[s.team] = `${s.group}${s.seed}`;
        if (s.elo != null) bracket.elo[s.team] = s.elo;
      }
      if (s.from) bracket.consumer[s.from] = { id: m.id, side };
    });
  });
}

function occupant(slot) { return slot.team || bracket.winners[slot.from] || null; }

function winProb(a, b) {
  const ea = bracket.elo[a], eb = bracket.elo[b];
  if (ea == null || eb == null) return null;
  return 100 / (1 + Math.pow(10, (eb - ea) / 400));
}

function fmtMatchDate(iso) {
  if (!iso) return "date TBD";
  return new Date(iso + "T00:00:00")
    .toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

/* A result only invalidates the ties its winner went on to play in — flipping a
   pre-quarter shouldn't wipe picks in the other half of the draw. */
function invalidate(matchId, staleTeam) {
  const c = bracket.consumer[matchId];
  if (!c) return;
  if (bracket.winners[c.id] === staleTeam) {
    delete bracket.winners[c.id];
    invalidate(c.id, staleTeam);
  }
}

function slotEl(m, side) {
  const s = m[side];
  const team = occupant(s);
  const btn = el("button", "bk-slot");
  btn.dataset.match = m.id;
  btn.dataset.side = side;
  if (!team) {
    btn.className = "bk-slot tbd";
    btn.disabled = true;
    btn.innerHTML = `<span class="bk-seed">·</span><span class="bk-team">Winner of ${s.from}</span>`;
    return btn;
  }
  const other = occupant(m[side === "a" ? "b" : "a"]);
  const decided = bracket.winners[m.id];
  if (decided === team) btn.classList.add("won");
  else if (decided) btn.classList.add("out");
  if (team === currentSeriesData().gladiators) btn.classList.add("us");
  btn.dataset.team = team;
  const p = other ? winProb(team, other) : null;
  btn.innerHTML =
    `<span class="bk-seed">${bracket.seed[team] || "·"}</span>
     <span class="bk-team">${team}</span>
     <span class="bk-prob">${p == null ? "" : Math.round(p) + "%"}</span>`;
  return btn;
}

function matchEl(m) {
  const card = el("div", "bk-match");
  card.dataset.id = m.id;
  const us = currentSeriesData().gladiators;
  if (occupant(m.a) === us || occupant(m.b) === us) card.classList.add("ours");
  if (bracket.winners[m.id]) card.classList.add("decided");
  card.appendChild(el("div", "bk-meta", `${m.id} <span>${fmtMatchDate(m.date)}</span>`));
  card.appendChild(slotEl(m, "a"));
  card.appendChild(slotEl(m, "b"));
  return card;
}

function drawWires(board, svg) {
  const br = board.getBoundingClientRect();
  svg.setAttribute("width", board.scrollWidth);
  svg.setAttribute("height", board.scrollHeight);
  svg.innerHTML = "";
  Object.keys(bracket.consumer).forEach((fromId) => {
    const c = bracket.consumer[fromId];
    const src = board.querySelector(`.bk-match[data-id="${fromId}"]`);
    const dst = board.querySelector(`.bk-match[data-id="${c.id}"]`);
    if (!src || !dst) return;
    const s = src.getBoundingClientRect(), d = dst.getBoundingClientRect();
    const x1 = s.right - br.left, y1 = s.top - br.top + s.height / 2;
    const x2 = d.left - br.left, y2 = d.top - br.top + d.height / 2;
    const xm = x1 + (x2 - x1) / 2;
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", `M${x1},${y1} H${xm} V${y2} H${x2}`);
    path.setAttribute("class", "bk-wire" + (bracket.winners[fromId] ? " live" : ""));
    svg.appendChild(path);
  });
}

/* The advancing team physically travels to its new slot — a fixed-position ghost tweened
   from the clicked chip to where that chip now lives a round later. */
function fly(fromRect, toEl, label) {
  const to = toEl.getBoundingClientRect();
  const ghost = el("div", "bk-ghost", label);
  ghost.style.cssText =
    `left:${fromRect.left}px; top:${fromRect.top}px; width:${fromRect.width}px; height:${fromRect.height}px;`;
  document.body.appendChild(ghost);
  requestAnimationFrame(() => {
    ghost.style.transform = `translate(${to.left - fromRect.left}px, ${to.top - fromRect.top}px)`;
    ghost.style.opacity = "0";
  });
  setTimeout(() => ghost.remove(), 620);
}

function advance(matchId, side, srcEl) {
  const m = bracket.byId[matchId];
  const team = occupant(m[side]);
  if (!team) return;
  const prev = bracket.winners[matchId];
  if (prev === team) {           // clicking the winner again undoes the result
    delete bracket.winners[matchId];
    invalidate(matchId, team);
    renderBracket();
    return;
  }
  const srcRect = srcEl.getBoundingClientRect();
  bracket.winners[matchId] = team;
  if (prev) invalidate(matchId, prev);
  renderBracket();
  const c = bracket.consumer[matchId];
  const target = c && document.querySelector(`.bk-slot[data-match="${c.id}"][data-side="${c.side}"]`);
  if (target) fly(srcRect, target, team);
}

/* Fills the whole bracket a round at a time so the result rolls forward as a wave
   rather than appearing all at once. */
let autoTimers = [];
function autoPick() {
  autoTimers.forEach(clearTimeout);
  autoTimers = [];
  bracket.winners = {};
  renderBracket();
  bracketData().rounds.forEach((r, i) => {
    autoTimers.push(setTimeout(() => {
      bracketData().matches.filter((m) => m.round === r.key).forEach((m) => {
        const a = occupant(m.a), b = occupant(m.b);
        if (!a || !b) return;
        bracket.winners[m.id] = (bracket.elo[a] || 0) >= (bracket.elo[b] || 0) ? a : b;
      });
      renderBracket();
    }, i * 500));
  });
}

function championEl() {
  const b = bracketData();
  const finalMatch = b.matches[b.matches.length - 1];
  const champ = bracket.winners[finalMatch.id];
  const col = el("div", "bk-col bk-col-champ");
  col.appendChild(el("div", "bk-col-head", "Champion"));
  const tile = el("div", "bk-champ" + (champ ? " crowned" : ""));
  tile.innerHTML = champ
    ? `<div class="bk-trophy">🏆</div><div class="bk-champ-team">${champ}</div>
       <div class="bk-champ-sub">${bracket.seed[champ] || ""} · ${fmtMatchDate(finalMatch.date)}</div>`
    : `<div class="bk-trophy dim">🏆</div><div class="bk-champ-sub">Play the bracket out</div>`;
  col.appendChild(tile);
  return col;
}

function renderBracket() {
  const box = $("bracket-content");
  box.innerHTML = "";
  const b = bracketData();
  if (!b) { box.appendChild(el("div", "empty-note", "No bracket for this series.")); return; }

  const bar = el("div", "bk-toolbar");
  const auto = el("button", "bk-btn", "⚡ Auto-pick by Elo");
  const reset = el("button", "bk-btn ghost", "Reset");
  auto.addEventListener("click", autoPick);
  reset.addEventListener("click", () => {
    autoTimers.forEach(clearTimeout); autoTimers = [];
    bracket.winners = {};
    renderBracket();
  });
  bar.appendChild(auto);
  bar.appendChild(reset);
  bar.appendChild(el("span", "bk-hint",
    "Click a team to send it through · click it again to undo · % is the Elo favourite"));
  box.appendChild(bar);

  const scroll = el("div", "bk-scroll");
  const board = el("div", "bk-board");
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "bk-wires");
  board.appendChild(svg);

  b.rounds.forEach((r) => {
    const col = el("div", "bk-col");
    col.appendChild(el("div", "bk-col-head", r.label));
    const stack = el("div", "bk-stack");
    b.matches.filter((m) => m.round === r.key).forEach((m) => stack.appendChild(matchEl(m)));
    col.appendChild(stack);
    board.appendChild(col);
  });
  board.appendChild(championEl());
  scroll.appendChild(board);
  box.appendChild(scroll);
  /* Measured synchronously, not in requestAnimationFrame: rAF never fires while the tab
     is in the background, so a page opened in a new tab rendered its bracket with no
     connectors and never repaired itself once you switched to it. getBoundingClientRect
     forces layout anyway, so the measurements here are just as good. */
  drawWires(board, svg);
}

/* Delegated: the board is rebuilt on every pick, so per-node listeners would be churn. */
function wireBracket() {
  const box = $("bracket-content");
  box.addEventListener("click", (e) => {
    const slot = e.target.closest(".bk-slot");
    if (slot && !slot.disabled) advance(slot.dataset.match, slot.dataset.side, slot);
  });
  box.addEventListener("mouseover", (e) => {
    const slot = e.target.closest(".bk-slot[data-team]");
    if (slot) traceTeam(slot.dataset.team);
  });
  box.addEventListener("mouseout", (e) => {
    if (e.target.closest(".bk-slot[data-team]")) traceTeam(null);
  });
  const redraw = () => {
    const board = document.querySelector(".bk-board");
    if (board) drawWires(board, board.querySelector(".bk-wires"));
  };
  window.addEventListener("resize", redraw);
  /* A tab that was hidden when it loaded may have laid out at a different width. */
  document.addEventListener("visibilitychange", () => { if (!document.hidden) redraw(); });
}

function traceTeam(team) {
  document.querySelectorAll(".bk-slot.trace").forEach((s) => s.classList.remove("trace"));
  if (!team) return;
  document.querySelectorAll(`.bk-slot[data-team="${CSS.escape(team)}"]`)
    .forEach((s) => s.classList.add("trace"));
}

/* ── Qualified ─────────────────────────────────────────────────────── */
function qualifiedTable(g) {
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
    wrap.appendChild(qualifiedTable(g));
    if (g.cutLine && g.cutLine.ptsBehind != null) {
      wrap.appendChild(el("div", "doc-note",
        `${g.cutLine.team} finished ${g.cutLine.ptsBehind} point${g.cutLine.ptsBehind === 1 ? "" : "s"} outside the cut.`));
    }
    box.appendChild(wrap);
  });
}

/* ── Wiring ────────────────────────────────────────────────────────── */
function renderAll() {
  indexBracket();
  renderOurTie();
  renderBracket();
  renderQualified();
}

renderDataUpdated();
buildSeriesPills();
wireBracket();
renderAll();
