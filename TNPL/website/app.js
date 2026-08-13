/* MOVI site — recomputes the index live from raw components (data.js). */
"use strict";

const DEFAULT_MIN_MATCHES = 4;   // TNPL's league stage is 7 matches (IPL: 14) — see middle_order_index.py
const DEFAULT_POS_MIN = 4.0;
const POS_MAX = 7;
const MATCH_OPTIONS = [4, 5, 6, 7, 8, 9, 10];
const POS_OPTIONS = [3.75, 3.80, 3.85, 3.90, 3.95, 4.00];
const COMP_LABELS = [
  ["z_volume", "Volume (runs/inns)"],
  ["z_efficiency", "Efficiency (strike rate)"],
  ["z_finishing", "Finishing (death overs)"],
  ["z_consistency", "Consistency (median)"],
];

const ROWS = MOVI_DATA.comp.map(r =>
  Object.fromEntries(MOVI_DATA.compCols.map((c, i) => [c, r[i]])));
const OC = MOVI_DATA.ocWinners.map(([season, batter, runs, sr]) => ({ season, batter, runs, sr }));
const RECOGNITION = new Map(MOVI_DATA.recognition.map(([s, b, a]) => [`${s}|${b}`, a]));

const state = { minMatches: DEFAULT_MIN_MATCHES, posMin: DEFAULT_POS_MIN };

/* ── Index computation (mirrors src/middle_order_index.py) ──────────── */
function computeMovi(minMatches, posMin) {
  const pool = ROWS.filter(r =>
    r.matches >= minMatches && r.avg_pos >= posMin && r.avg_pos <= POS_MAX);
  const bySeason = new Map();
  pool.forEach(r => {
    if (!bySeason.has(r.season)) bySeason.set(r.season, []);
    bySeason.get(r.season).push({ ...r });
  });

  const zscore = (vals) => {
    const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
    const sd = vals.length > 1
      ? Math.sqrt(vals.reduce((a, b) => a + (b - mean) ** 2, 0) / (vals.length - 1))
      : 0;
    return vals.map(v => (sd > 0 ? (v - mean) / sd : 0));
  };

  const out = [];
  for (const rows of bySeason.values()) {
    const known = rows.filter(r => r.death_sr != null).map(r => r.death_sr);
    const deathMean = known.length ? known.reduce((a, b) => a + b, 0) / known.length : 0;
    rows.forEach(r => { r.death_sr_f = r.death_sr == null ? deathMean : r.death_sr; });
    const pairs = [["mean_rpi", "z_volume"], ["sr", "z_efficiency"],
                   ["death_sr_f", "z_finishing"], ["median_rpi", "z_consistency"]];
    pairs.forEach(([col, zc]) => {
      const zs = zscore(rows.map(r => r[col]));
      rows.forEach((r, i) => { r[zc] = zs[i]; });
    });
    rows.forEach(r => {
      r.index = (r.z_volume + r.z_efficiency + r.z_finishing + r.z_consistency) / 4;
    });
    rows.sort((a, b) => b.index - a.index);
    rows.forEach((r, i) => { r.season_rank = i + 1; });
    out.push(...rows);
  }
  return out.sort((a, b) => a.season - b.season || a.season_rank - b.season_rank);
}

const bestPerSeason = (moi) => moi.filter(r => r.season_rank === 1);

/* ── Small helpers ──────────────────────────────────────────────────── */
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

/* ── Hero stats (fixed at default thresholds) ───────────────────────── */
function heroStats() {
  const best = bestPerSeason(computeMovi(DEFAULT_MIN_MATCHES, DEFAULT_POS_MIN));
  const ocBySeason = new Map(OC.map(o => [o.season, o]));
  const faster = best.filter(b => {
    const oc = ocBySeason.get(b.season);
    return oc && b.sr > oc.sr;
  }).length;
  const unrec = best.filter(b => !RECOGNITION.get(`${b.season}|${b.batter}`)).length;
  const n = best.length;
  countUp($("hs-seasons"), n, v => `${v}`);
  countUp($("hs-faster"), faster, v => `${v} / ${n}`);
  countUp($("hs-unrec"), unrec, v => `${v} / ${n}`);
}

function countUp(node, target, render) {
  const dur = 1300, t0 = performance.now();
  const tick = (t) => {
    const p = Math.min((t - t0) / dur, 1);
    node.textContent = render(Math.round(target * (1 - Math.pow(1 - p, 3))));
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

/* ── Controls ───────────────────────────────────────────────────────── */
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
  if (state.minMatches !== DEFAULT_MIN_MATCHES || state.posMin !== DEFAULT_POS_MIN) {
    node.textContent = `Showing MOVI for positions ${state.posMin}–${POS_MAX} at a ` +
      `${state.minMatches}-match minimum (defaults: ${DEFAULT_POS_MIN}–${POS_MAX}, ` +
      `${DEFAULT_MIN_MATCHES} matches).`;
  } else {
    node.textContent = "";
  }
}

/* ── Champions grid + repeats ───────────────────────────────────────── */
function renderChampions(best) {
  const grid = $("champ-grid");
  grid.innerHTML = "";
  const counts = new Map();
  best.forEach(b => counts.set(b.batter, (counts.get(b.batter) || 0) + 1));
  best.forEach(b => {
    const c = el("div", "champ" + (counts.get(b.batter) >= 2 ? " multi" : ""));
    c.append(
      el("div", "champ-season", String(b.season)),
      el("div", "champ-name", b.batter),
      el("div", "champ-team", b.team),
      el("div", "champ-movi gold", fmt(b.index)),
      el("div", "champ-meta", `${b.runs} runs · SR ${fmt(b.sr, 0)}`),
    );
    bindTooltip(c, `<b>${b.batter}</b> — ${b.team}<br>MOVI ${fmt(b.index)} · avg pos ${fmt(b.avg_pos, 1)}<br>` +
      `${b.matches} matches · ${b.runs} runs · SR ${fmt(b.sr, 1)}`);
    grid.appendChild(c);
  });

  const repeats = [...counts.entries()].filter(([, n]) => n >= 2)
    .sort((a, b) => b[1] - a[1]);
  $("repeats").innerHTML = repeats.length
    ? "★ The uncrowned regulars — " + repeats.map(([name, n]) =>
        `<strong>${name}</strong> (${n}×)`).join(" · ")
    : "";
}

/* ── Season explorer ────────────────────────────────────────────────── */
function renderExplorer(moi) {
  const seasons = [...new Set(moi.map(r => r.season))];
  const sel = $("season-select");
  const prev = Number(sel.value);
  sel.innerHTML = "";
  seasons.forEach(s => sel.appendChild(el("option", null, String(s))));
  sel.value = seasons.includes(prev) ? String(prev) : String(seasons[seasons.length - 1]);

  const season = Number(sel.value);
  const sdf = moi.filter(r => r.season === season).slice(0, 8);
  $("explorer-title").textContent = `Top middle-order batsmen — ${season}`;

  const chart = $("explorer-bars");
  chart.innerHTML = "";
  const max = Math.max(...sdf.map(r => r.index), 0.01);
  sdf.forEach((r, i) => {
    const row = el("div", "bar-row");
    const fill = el("div", "bar-fill " + (i === 0 ? "gold" : "blue"));
    const track = el("div", "bar-track");
    track.appendChild(fill);
    row.append(el("div", "bar-name", r.batter), track,
               el("div", "bar-val", fmt(r.index)));
    bindTooltip(row, `<b>${r.batter}</b> — ${r.team}<br>MOVI ${fmt(r.index)}<br>` +
      `Avg position ${fmt(r.avg_pos, 1)} · ${r.matches} matches<br>` +
      `${r.runs} runs · SR ${fmt(r.sr, 1)}` +
      (r.death_sr != null ? ` · Death SR ${fmt(r.death_sr, 1)}` : ""));
    chart.appendChild(row);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      fill.style.width = `${Math.max(r.index / max, 0) * 100}%`;
    }));
  });

  renderBreakdown(sdf[0]);
}

function renderBreakdown(winner) {
  const box = $("breakdown");
  box.innerHTML = "";
  if (!winner) { $("breakdown-title").textContent = ""; return; }
  $("breakdown-title").textContent = `What set ${winner.batter} apart`;
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

/* ── Dumbbell ───────────────────────────────────────────────────────── */
function renderDumbbell(best) {
  const ocBySeason = new Map(OC.map(o => [o.season, o]));
  const rows = best.filter(b => ocBySeason.has(b.season)).map(b => ({
    season: b.season, moName: b.batter, moSr: b.sr,
    ocName: ocBySeason.get(b.season).batter, ocSr: ocBySeason.get(b.season).sr,
  }));

  const W = 760, rowH = 32, padT = 26, padB = 34, padL = 52, padR = 18;
  const H = padT + rows.length * rowH + padB;
  const svg = $("dumbbell");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = "";
  const NS = "http://www.w3.org/2000/svg";
  const node = (tag, attrs) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    return n;
  };

  const srs = rows.flatMap(r => [r.moSr, r.ocSr]);
  const lo = Math.floor(Math.min(...srs) / 10) * 10 - 5;
  const hi = Math.ceil(Math.max(...srs) / 10) * 10 + 5;
  const x = (sr) => padL + (sr - lo) / (hi - lo) * (W - padL - padR);
  const y = (i) => padT + i * rowH + rowH / 2;

  for (let t = Math.ceil(lo / 20) * 20; t <= hi; t += 20) {
    svg.appendChild(node("line", { x1: x(t), x2: x(t), y1: padT, y2: H - padB,
      stroke: "#222a3e", "stroke-width": 1 }));
    const lbl = node("text", { x: x(t), y: H - padB + 20, fill: "#6b7384",
      "font-size": 11, "text-anchor": "middle" });
    lbl.textContent = t;
    svg.appendChild(lbl);
  }
  const axis = node("text", { x: (padL + W - padR) / 2, y: H - 2, fill: "#6b7384",
    "font-size": 11, "text-anchor": "middle" });
  axis.textContent = "Season strike rate (runs per 100 balls)";
  svg.appendChild(axis);

  rows.forEach((r, i) => {
    const yy = y(i);
    const lbl = node("text", { x: padL - 10, y: yy + 4, fill: "#939bad",
      "font-size": 11.5, "text-anchor": "end" });
    lbl.textContent = r.season;
    svg.appendChild(lbl);
    svg.appendChild(node("line", { x1: x(r.ocSr), x2: x(r.moSr), y1: yy, y2: yy,
      stroke: "#4a5368", "stroke-width": 2 }));
    const oc = node("circle", { cx: x(r.ocSr), cy: yy, r: 6.5, fill: "#e07b39",
      stroke: "#7a4a1f", "stroke-width": 1 });
    const mo = node("circle", { cx: x(r.moSr), cy: yy, r: 6.5, fill: "#3a86ff",
      stroke: "#1c4f9c", "stroke-width": 1 });
    bindTooltip(oc, `<b>${r.ocName}</b> (${r.season})<br>Run-leader · SR ${fmt(r.ocSr, 1)}`);
    bindTooltip(mo, `<b>${r.moName}</b> (${r.season})<br>Best middle order · SR ${fmt(r.moSr, 1)}`);
    svg.append(oc, mo);
  });

  const faster = rows.filter(r => r.moSr > r.ocSr).length;
  const gap = rows.reduce((a, r) => a + (r.moSr - r.ocSr), 0) / rows.length;
  $("dumbbell-caption").innerHTML =
    `In <strong>${faster} of ${rows.length}</strong> seasons the best middle-order batsman ` +
    `struck faster than the season's leading run-scorer — by an average of ` +
    `<strong>${fmt(gap, 0)} runs per 100 balls</strong>. Hover the dots for names.`;
}

/* ── Recognition (fixed at default thresholds) ──────────────────────── */
function renderRecognition() {
  const best = bestPerSeason(computeMovi(DEFAULT_MIN_MATCHES, DEFAULT_POS_MIN));
  const tbody = $("rec-table").querySelector("tbody");
  tbody.innerHTML = "";
  let unrec = 0;
  best.forEach(b => {
    const award = RECOGNITION.get(`${b.season}|${b.batter}`);
    if (!award) unrec++;
    const tr = el("tr");
    tr.append(
      el("td", null, String(b.season)),
      el("td", null, b.batter),
      el("td", award ? "awarded" : "noaward", award || "—"),
    );
    tbody.appendChild(tr);
  });
  $("rec-bignum").textContent = `${unrec} / ${best.length}`;
}

/* ── Wiring ─────────────────────────────────────────────────────────── */
function renderAll() {
  const moi = computeMovi(state.minMatches, state.posMin);
  const best = bestPerSeason(moi);
  thresholdNote();
  renderChampions(best);
  renderExplorer(moi);
  renderDumbbell(best);
}

buildPills("pills-matches", MATCH_OPTIONS, String,
  () => state.minMatches, v => { state.minMatches = v; });
buildPills("pills-pos", POS_OPTIONS, v => v.toFixed(2),
  () => state.posMin, v => { state.posMin = v; });
$("season-select").addEventListener("change", () =>
  renderExplorer(computeMovi(state.minMatches, state.posMin)));

const observer = new IntersectionObserver((entries) => {
  entries.forEach(e => { if (e.isIntersecting) e.target.classList.add("visible"); });
}, { threshold: 0.12 });
document.querySelectorAll(".reveal").forEach(s => observer.observe(s));

heroStats();
renderRecognition();
renderAll();
