/* TNPL 2026 (in-progress season) — provisional MOVI leaderboard.
   Trimmed from app.js: single season, no cross-season champions/dumbbell/
   recognition sections since those need a finished season to mean anything. */
"use strict";

const MIN_MATCHES = MOVI_DATA_2026.minMatches;
const POS_MIN = 4.0;
const POS_MAX = 7;
const COMP_LABELS = [
  ["z_volume", "Volume (runs/inns)"],
  ["z_efficiency", "Efficiency (strike rate)"],
  ["z_finishing", "Finishing (death overs)"],
  ["z_consistency", "Consistency (median)"],
];
const MATCH_OPTIONS = [2, 3, 4, 5, 6];
const POS_OPTIONS = [3.75, 3.80, 3.85, 3.90, 3.95, 4.00];

const ROWS = MOVI_DATA_2026.comp.map(r =>
  Object.fromEntries(MOVI_DATA_2026.compCols.map((c, i) => [c, r[i]])));

const state = { minMatches: MIN_MATCHES, posMin: POS_MIN };

function computeMovi(minMatches, posMin) {
  const pool = ROWS.filter(r =>
    r.matches >= minMatches && r.avg_pos >= posMin && r.avg_pos <= POS_MAX);

  const zscore = (vals) => {
    const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
    const sd = vals.length > 1
      ? Math.sqrt(vals.reduce((a, b) => a + (b - mean) ** 2, 0) / (vals.length - 1))
      : 0;
    return vals.map(v => (sd > 0 ? (v - mean) / sd : 0));
  };

  const rows = pool.map(r => ({ ...r }));
  const known = rows.filter(r => r.death_sr != null).map(r => r.death_sr);
  const deathMean = known.length ? known.reduce((a, b) => a + b, 0) / known.length : 0;
  rows.forEach(r => { r.death_sr_f = r.death_sr == null ? deathMean : r.death_sr; });
  const pairs = [["mean_rpi", "z_volume"], ["sr", "z_efficiency"],
                 ["death_sr_f", "z_finishing"], ["median_rpi", "z_consistency"]];
  pairs.forEach(([col, zc]) => {
    const zs = zscore(rows.map(r => r[col]));
    rows.forEach((r, i) => { r[zc] = zs[i]; });
  });
  rows.forEach(r => { r.index = (r.z_volume + r.z_efficiency + r.z_finishing + r.z_consistency) / 4; });
  rows.sort((a, b) => b.index - a.index);
  rows.forEach((r, i) => { r.season_rank = i + 1; });
  return rows;
}

const $ = (id) => document.getElementById(id);
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
};
const fmt = (v, d = 2) => v.toFixed(d);

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

function buildPills(containerId, options, format, get, set) {
  const box = $(containerId);
  options.forEach(opt => {
    const b = el("button", "pill", format(opt));
    b.addEventListener("click", () => {
      set(opt);
      box.querySelectorAll(".pill").forEach(p => p.classList.remove("active"));
      b.classList.add("active");
      renderAll();
    });
    if (opt === get()) b.classList.add("active");
    box.appendChild(b);
  });
}

function thresholdNote() {
  const node = $("threshold-note");
  if (state.minMatches !== MIN_MATCHES || state.posMin !== POS_MIN) {
    node.textContent = `Showing MOVI for positions ${state.posMin}–${POS_MAX} at a ` +
      `${state.minMatches}-match minimum (defaults: ${POS_MIN}–${POS_MAX}, ${MIN_MATCHES} matches).`;
  } else {
    node.textContent = "";
  }
}

function renderBars(moi) {
  const sdf = moi.slice(0, 10);
  const chart = $("explorer-bars");
  chart.innerHTML = "";
  const max = Math.max(...sdf.map(r => r.index), 0.01);
  sdf.forEach((r, i) => {
    const row = el("div", "bar-row");
    const fill = el("div", "bar-fill " + (i === 0 ? "gold" : "blue"));
    const track = el("div", "bar-track");
    track.appendChild(fill);
    row.append(el("div", "bar-name", r.batter), track, el("div", "bar-val", fmt(r.index)));
    bindTooltip(row, `<b>${r.batter}</b> — ${r.team}<br>MOVI ${fmt(r.index)}<br>` +
      `Avg position ${fmt(r.avg_pos, 1)} · ${r.matches} matches so far<br>` +
      `${r.runs} runs · SR ${fmt(r.sr, 1)}` +
      (r.death_sr != null ? ` · Death SR ${fmt(r.death_sr, 1)}` : ""));
    chart.appendChild(row);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      fill.style.width = `${Math.max(r.index / max, 0) * 100}%`;
    }));
  });
  renderBreakdown(sdf[0]);
  renderLeaderNote(sdf[0]);
}

function renderBreakdown(winner) {
  const box = $("breakdown");
  box.innerHTML = "";
  if (!winner) { $("breakdown-title").textContent = ""; return; }
  $("breakdown-title").textContent = `What's setting ${winner.batter} apart so far`;
  const vals = COMP_LABELS.map(([k]) => winner[k]);
  const lim = Math.max(...vals.map(Math.abs), 0.5) * 1.15;
  COMP_LABELS.forEach(([key, label]) => {
    const v = winner[key];
    const row = el("div", "div-row");
    const track = el("div", "div-track");
    const fill = el("div", "div-fill " + (v >= 0 ? "pos" : "neg"));
    const val = el("div", "div-val", (v >= 0 ? "+" : "") + fmt(v));
    track.append(fill, val);
    row.append(el("div", "div-name", label), track);
    box.appendChild(row);
    const halfPct = Math.abs(v) / lim * 50;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      fill.style.width = `${halfPct}%`;
      fill.style.left = v >= 0 ? "50%" : `${50 - halfPct}%`;
      val.style.left = v >= 0 ? `calc(${50 + halfPct}% + 6px)` : "";
      val.style.right = v >= 0 ? "" : `calc(${50 + halfPct}% + 6px)`;
    }));
  });
}

function renderLeaderNote(moviLeader) {
  const node = $("leader-note");
  if (!moviLeader) { node.textContent = ""; return; }
  const [name, runs, sr] = MOVI_DATA_2026.runsLeader;
  const cmp = moviLeader.sr > sr ? "faster than" : moviLeader.sr < sr ? "slower than" : "the same as";
  node.innerHTML = `So far this season's runs leader is <strong>${name}</strong> ` +
    `(${runs} runs, SR ${fmt(sr, 1)}). The provisional MOVI #1, <strong>${moviLeader.batter}</strong>, ` +
    `is striking at <strong>${fmt(moviLeader.sr, 1)}</strong> — ${cmp} the runs leader.`;
}

function renderAll() {
  const moi = computeMovi(state.minMatches, state.posMin);
  thresholdNote();
  renderBars(moi);
}

buildPills("pills-matches", MATCH_OPTIONS, String, () => state.minMatches, v => { state.minMatches = v; });
buildPills("pills-pos", POS_OPTIONS, v => v.toFixed(2), () => state.posMin, v => { state.posMin = v; });

$("progress-note").textContent =
  `${MOVI_DATA_2026.matchesPlayed} of ${MOVI_DATA_2026.matchesTotal} matches played (league stage in progress).`;

const observer = new IntersectionObserver((entries) => {
  entries.forEach(e => { if (e.isIntersecting) e.target.classList.add("visible"); });
}, { threshold: 0.12 });
document.querySelectorAll(".reveal").forEach(s => observer.observe(s));

renderAll();
