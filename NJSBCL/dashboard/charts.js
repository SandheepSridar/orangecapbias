/* NJSBCL Scout — Gladiators season charts (reads the same NJSBCL_DATA as app.js). */
"use strict";

const $ = (id) => document.getElementById(id);
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
};

const tooltip = $("tooltip");
function bindTooltip(target, html) {
  target.addEventListener("mousemove", (ev) => {
    tooltip.innerHTML = html;
    tooltip.hidden = false;
    const pad = 14;
    let x = ev.clientX + pad, y = ev.clientY + pad;
    const r = tooltip.getBoundingClientRect();
    if (x + r.width > window.innerWidth - 8) x = ev.clientX - r.width - pad;
    if (y + r.height > window.innerHeight - 8) y = ev.clientY - r.height - pad;
    tooltip.style.left = x + "px";
    tooltip.style.top = y + "px";
  });
  target.addEventListener("mouseleave", () => { tooltip.hidden = true; });
}

const SERIES_KEYS = Object.keys(NJSBCL_DATA.series);
const state = { series: SERIES_KEYS[0], unavailable: new Set() };

function currentSeriesData() { return NJSBCL_DATA.series[state.series]; }

/* ── Best XI selection (ported 1:1 from build_data.py's select_xi) ──── */
function selectXI(roster) {
  const byPlayer = {};
  roster.forEach((r) => { byPlayer[r.player] = r; });
  const picked = [];
  const pick = (p) => { if (p != null && !picked.includes(p) && byPlayer[p]) picked.push(p); };

  const keeper = roster.find((r) => r.isKeeper);
  if (keeper) pick(keeper.player);

  const battersRanked = roster.filter((r) => r.battingScore !== null).sort((a, b) => b.battingScore - a.battingScore);
  for (const r of battersRanked) {
    if (picked.length >= 6) break;
    pick(r.player);
  }

  const bowlersRanked = roster.filter((r) => r.bowlingScore !== null).sort((a, b) => b.bowlingScore - a.bowlingScore);
  const bowlingCount = () => picked.filter((p) => byPlayer[p].bowlingScore !== null).length;
  for (const r of bowlersRanked) {
    if (bowlingCount() >= 5 || picked.length >= 11) break;
    pick(r.player);
  }

  const remaining = roster
    .filter((r) => !picked.includes(r.player))
    .sort((a, b) => ((b.battingScore || 0) + (b.bowlingScore || 0)) - ((a.battingScore || 0) + (a.bowlingScore || 0)));
  for (const r of remaining) {
    if (picked.length >= 11) break;
    pick(r.player);
  }

  return picked.slice(0, 11).map((p) => {
    const r = byPlayer[p];
    const role = r.isKeeper ? "Wicketkeeper"
      : (r.battingScore !== null && r.bowlingScore !== null) ? "All-rounder"
      : r.battingScore !== null ? "Batter" : "Bowler";
    return { ...r, role };
  });
}

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
      state.unavailable = new Set();
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

/* ── Best XI ───────────────────────────────────────────────────────── */
const ROLE_CLASS = {
  "Wicketkeeper": "keeper", "All-rounder": "allrounder", "Batter": "batter", "Bowler": "bowler",
};

function renderAvailabilityChips() {
  const s = currentSeriesData();
  const roster = s.gladiatorsCharts.bestXI.roster;
  const box = $("avail-chips");
  box.innerHTML = "";
  [...roster]
    .sort((a, b) => a.player.localeCompare(b.player))
    .forEach((r) => {
      const isOut = state.unavailable.has(r.player);
      const chip = el("button", `avail-chip${isOut ? " unavailable" : ""}`, r.player);
      chip.addEventListener("click", () => {
        if (state.unavailable.has(r.player)) state.unavailable.delete(r.player);
        else state.unavailable.add(r.player);
        renderAvailabilityChips();
        renderBestXI();
      });
      box.appendChild(chip);
    });
}

function renderBestXI() {
  const s = currentSeriesData();
  const gc = s.gladiatorsCharts;
  const box = $("bestxi-list");
  const note = $("bestxi-note");
  box.innerHTML = "";

  const roster = gc.bestXI.roster.filter((r) => !state.unavailable.has(r.player));
  const players = selectXI(roster);

  if (state.unavailable.size) {
    note.hidden = false;
    note.textContent = players.length < 11
      ? `${state.unavailable.size} player(s) marked unavailable — only ${players.length} qualifying options left in the squad.`
      : `${state.unavailable.size} player(s) marked unavailable — XI reshuffled from the rest of the squad.`;
  } else {
    note.hidden = true;
  }

  if (!players.length) {
    box.appendChild(el("div", "empty-note", "Not enough qualifying players available."));
    return;
  }
  players.forEach((p, i) => {
    const card = el("div", "xi-card");
    const rank = el("div", `xi-rank ${ROLE_CLASS[p.role] || ""}`, String(i + 1));
    const body = el("div", "xi-body");
    const top = el("div", "xi-top");
    top.append(
      el("span", "xi-name", p.player),
      el("span", `xi-role ${ROLE_CLASS[p.role] || ""}`, p.role),
    );
    const stats = el("div", "xi-stats");
    if (p.battingStats) {
      stats.appendChild(el("span", "xi-stat",
        `bat: <b>${p.battingStats.runs}</b>r · avg ${p.battingStats.avg} · SR ${p.battingStats.sr}`));
    }
    if (p.bowlingStats) {
      stats.appendChild(el("span", "xi-stat",
        `bowl: <b>${p.bowlingStats.wickets}</b>w · econ ${p.bowlingStats.econ} · dot ${p.bowlingStats.dotPct}%`));
    }
    body.append(top, stats);
    card.append(rank, body);
    box.appendChild(card);
  });
}

/* ── Elo trajectory ───────────────────────────────────────────────── */
function renderEloChart() {
  const s = currentSeriesData();
  const history = s.gladiatorsCharts.eloHistory;
  const box = $("elo-chart");
  box.innerHTML = "";
  if (!history.length) {
    box.appendChild(el("div", "empty-note", "No completed matches yet this season."));
    return;
  }
  const W = 800, H = 220, padL = 36, padR = 16, padT = 20, padB = 24;
  const elos = history.map((h) => h.elo);
  const minE = Math.min(...elos, 1500) - 15;
  const maxE = Math.max(...elos, 1500) + 15;
  const n = history.length;
  const x = (i) => padL + (n > 1 ? (i / (n - 1)) * (W - padL - padR) : (W - padL - padR) / 2);
  const y = (v) => H - padB - ((v - minE) / (maxE - minE)) * (H - padT - padB);

  const points = history.map((h, i) => `${x(i)},${y(h.elo)}`).join(" ");
  const resultColor = (r) => (r === "Win" ? "var(--win)" : r === "Loss" ? "var(--loss)" : "var(--muted)");

  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("class", "elo-svg");

  const baseline = document.createElementNS(svgNS, "line");
  baseline.setAttribute("x1", padL); baseline.setAttribute("x2", W - padR);
  baseline.setAttribute("y1", y(1500)); baseline.setAttribute("y2", y(1500));
  baseline.setAttribute("class", "elo-baseline");
  baseline.setAttribute("vector-effect", "non-scaling-stroke");
  svg.appendChild(baseline);

  const label1500 = document.createElementNS(svgNS, "text");
  label1500.setAttribute("x", padL + 2); label1500.setAttribute("y", y(1500) - 4);
  label1500.setAttribute("class", "elo-baseline-label");
  label1500.textContent = "1500 start";
  svg.appendChild(label1500);

  const poly = document.createElementNS(svgNS, "polyline");
  poly.setAttribute("points", points);
  poly.setAttribute("class", "elo-line");
  poly.setAttribute("vector-effect", "non-scaling-stroke");
  svg.appendChild(poly);

  history.forEach((h, i) => {
    const dot = document.createElementNS(svgNS, "circle");
    dot.setAttribute("cx", x(i)); dot.setAttribute("cy", y(h.elo));
    dot.setAttribute("r", 4.5);
    dot.setAttribute("fill", resultColor(h.result));
    dot.setAttribute("class", "elo-dot");
    bindTooltip(dot, `vs <b>${h.opponent}</b><br>${h.result} · Elo now <b>${h.elo}</b>`);
    svg.appendChild(dot);
  });

  box.appendChild(svg);
  const legend = el("div", "elo-legend");
  legend.innerHTML = `
    <span><span class="elo-swatch" style="background:var(--win)"></span>Win</span>
    <span><span class="elo-swatch" style="background:var(--loss)"></span>Loss</span>
    <span><span class="elo-swatch" style="background:var(--muted)"></span>Tie</span>`;
  box.appendChild(legend);
}

/* ── Squad leaderboards ───────────────────────────────────────────── */
function renderLeaderboard(containerId, players, valueKey, labelFn, colorVar) {
  const box = $(containerId);
  box.innerHTML = "";
  if (!players || !players.length) {
    box.appendChild(el("div", "empty-note", "No data yet."));
    return;
  }
  const sorted = [...players].sort((a, b) => b[valueKey] - a[valueKey]);
  const max = sorted[0][valueKey] || 1;
  sorted.forEach((p) => {
    const row = el("div", "lb-row");
    const barWrap = el("div", "lb-bar-wrap");
    const bar = el("div", "lb-bar");
    bar.style.width = `${Math.max(4, (100 * p[valueKey]) / max)}%`;
    bar.style.background = colorVar;
    barWrap.appendChild(bar);
    row.append(el("div", "lb-name", p.player), barWrap, el("div", "lb-val", labelFn(p)));
    box.appendChild(row);
  });
}

/* ── Other season metrics ─────────────────────────────────────────── */
function renderOtherMetrics() {
  const s = currentSeriesData();
  const us = s.teams[s.gladiators];
  const grid = $("other-metrics-grid");
  grid.innerHTML = "";
  if (!us) return;

  const ha = us.homeAway;
  grid.appendChild(el("div", "metric-tile",
    `<h3>Home vs away this season</h3>
     <div style="font-size:1.5rem;font-weight:800;font-family:'Sora',sans-serif;">
       ${ha.home.winPct ?? "—"}% <span style="font-size:0.95rem;color:var(--muted);font-weight:600;">home</span>
       &nbsp;·&nbsp; ${ha.away.winPct ?? "—"}% <span style="font-size:0.95rem;color:var(--muted);font-weight:600;">away</span>
     </div>
     <div class="mt-note">${ha.home.wins}-${ha.home.matches - ha.home.wins} record at home,
       ${ha.away.wins}-${ha.away.matches - ha.away.wins} away.</div>`));

  const bc = us.battingCollapses;
  const leagueAvg = s.gladiatorsCharts.leagueAvgCollapsePct;
  grid.appendChild(el("div", "metric-tile",
    `<h3>Batting collapse rate</h3>
     <div style="font-size:1.5rem;font-weight:800;font-family:'Sora',sans-serif;">${bc.collapsePct}%</div>
     <div class="mt-note">${bc.collapseCount} of ${bc.totalInnings} innings this season
       (league average: ${leagueAvg}%).</div>`));

  const toss = us.toss;
  grid.appendChild(el("div", "metric-tile",
    `<h3>Toss performance</h3>
     <div style="font-size:0.92rem;">
       Batting first: ${toss.battingFirst.wins}/${toss.battingFirst.matches} won${toss.battingFirst.winPct != null ? ` (${toss.battingFirst.winPct}%)` : ""}<br>
       Chasing: ${toss.chasing.wins}/${toss.chasing.matches} won${toss.chasing.winPct != null ? ` (${toss.chasing.winPct}%)` : ""}
     </div>
     <div class="mt-note">${toss.reason}</div>`));
}

/* ── Wiring ────────────────────────────────────────────────────────── */
function renderAll() {
  const s = currentSeriesData();
  renderAvailabilityChips();
  renderBestXI();
  renderEloChart();
  renderLeaderboard("bat-leaderboard", s.gladiatorsCharts.battingLeaderboard, "runs",
    (p) => `${p.runs} (avg ${p.avg}, SR ${p.sr})`, "var(--gold)");
  renderLeaderboard("bowl-leaderboard", s.gladiatorsCharts.bowlingLeaderboard, "wickets",
    (p) => `${p.wickets}w (econ ${p.econ})`, "var(--blue)");
  renderOtherMetrics();
}

renderDataUpdated();
buildSeriesPills();
renderAll();
