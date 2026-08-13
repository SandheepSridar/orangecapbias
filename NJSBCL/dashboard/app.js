/* NJSBCL Scout — renders precomputed NJSBCL_DATA (see data.js / build_data.py). */
"use strict";

const DISMISSAL_COLORS = {
  "Caught": "var(--blue)",
  "Bowled": "var(--gold)",
  "LBW": "var(--orange)",
  "Run Out": "var(--grey)",
  "Stumped": "var(--teal)",
  "Caught & Bowled": "var(--purple)",
  "Retired": "var(--pink)",
  "Hit Wicket": "var(--pink)",
  "Handled Ball": "var(--grey)",
  "Other": "var(--grey)",
};

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
const state = {
  series: SERIES_KEYS[0],
  opponent: null,
  showAllFixtures: false,
};

function currentSeriesData() { return NJSBCL_DATA.series[state.series]; }
function currentUs() { const s = currentSeriesData(); return s.teams[s.gladiators]; }
function currentThem() { const s = currentSeriesData(); return s.teams[state.opponent]; }

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
      state.showAllFixtures = false;
      const opts = currentSeriesData().opponents;
      state.opponent = opts.includes(state.opponent) ? state.opponent : opts[0];
      box.querySelectorAll(".pill").forEach((p) => p.classList.remove("active"));
      b.classList.add("active");
      populateOpponentSelect();
      renderAll();
    });
    box.appendChild(b);
  });
}

function populateOpponentSelect() {
  const sel = $("opponent-select");
  const s = currentSeriesData();
  const prev = state.opponent;
  sel.innerHTML = "";
  s.opponents.forEach((opp) => sel.appendChild(el("option", null, opp)));
  state.opponent = s.opponents.includes(prev) ? prev : s.opponents[0];
  sel.value = state.opponent;
}

/* ── Win probability ───────────────────────────────────────────────── */
function eloWinPct(eloA, eloB) {
  return 100 / (1 + Math.pow(10, (eloB - eloA) / 400));
}

function renderWinProb() {
  const s = currentSeriesData();
  const us = currentUs(), them = currentThem();
  const card = $("winprob-card");
  card.innerHTML = "";
  if (!us || !them) return;
  const usPct = eloWinPct(us.elo, them.elo);
  const themPct = 100 - usPct;

  const labels = el("div", "winprob-labels");
  labels.innerHTML = `
    <span><span class="team us">${s.gladiators}</span><span class="pct gold">${usPct.toFixed(0)}%</span></span>
    <span><span class="pct" style="color:var(--blue)">${themPct.toFixed(0)}%</span><span class="team them">${state.opponent}</span></span>
  `;
  const bar = el("div", "winprob-bar");
  const segUs = el("div", "winprob-seg us");
  const segThem = el("div", "winprob-seg them");
  bar.append(segUs, segThem);
  const elo = el("div", "winprob-elo", `
    <span>Elo rating — <b class="gold">${s.gladiators}</b>: <b>${us.elo}</b></span>
    <span>Elo rating — <b style="color:var(--blue)">${state.opponent}</b>: <b>${them.elo}</b></span>
  `);
  card.append(labels, bar, elo);
  requestAnimationFrame(() => requestAnimationFrame(() => {
    segUs.style.width = usPct + "%";
    segThem.style.width = themPct + "%";
  }));
}

/* ── Fixtures ──────────────────────────────────────────────────────── */
const FIXTURES_HIGHLIGHT_COUNT = 3;

function renderFixtures() {
  const grid = $("fixture-grid");
  const toggle = $("fixtures-toggle");
  grid.innerHTML = "";
  const s = currentSeriesData();
  if (!s.upcoming.length) {
    grid.appendChild(el("div", "empty-note", "No upcoming fixtures scheduled."));
    toggle.hidden = true;
    return;
  }
  const us = currentUs();
  const visible = state.showAllFixtures ? s.upcoming : s.upcoming.slice(0, FIXTURES_HIGHLIGHT_COUNT);
  visible.forEach((m, i) => {
    const c = el("div", `fixture-card${i < FIXTURES_HIGHLIGHT_COUNT ? " highlighted" : ""}`);
    c.append(
      el("div", "fixture-date", `${m.date} · ${m.time}`),
      el("div", "fixture-opp", `vs ${m.opponent}`),
      el("div", "fixture-venue", m.venue),
    );
    const opp = s.teams[m.opponent];
    if (opp && opp.recentResults && opp.recentResults.length) {
      const form = el("div", "fixture-form");
      opp.recentResults.forEach((r) => {
        const dot = el("span", `form-dot ${r.result.toLowerCase()}`, r.result[0]);
        bindTooltip(dot, `${r.result} vs ${r.opponent}`);
        form.appendChild(dot);
      });
      c.appendChild(form);
    }
    if (us && opp) {
      const pct = Math.round(eloWinPct(us.elo, opp.elo));
      const badge = el("div", `fixture-winprob ${pct >= 50 ? "favored" : "underdog"}`, `${pct}% win probability`);
      bindTooltip(badge, `Elo — ${s.gladiators}: <b>${us.elo}</b> vs ${m.opponent}: <b>${opp.elo}</b>`);
      c.appendChild(badge);
    }
    grid.appendChild(c);
  });

  const remaining = s.upcoming.length - FIXTURES_HIGHLIGHT_COUNT;
  if (remaining <= 0) {
    toggle.hidden = true;
  } else {
    toggle.hidden = false;
    toggle.textContent = state.showAllFixtures
      ? "Show fewer"
      : `Show all ${s.upcoming.length} upcoming matches`;
  }
}

/* ── Toss advice ───────────────────────────────────────────────────── */
function tossBadgeText(rec) {
  if (rec === "bat") return "BAT FIRST";
  if (rec === "bowl") return "BOWL FIRST";
  if (rec === "even") return "EITHER WORKS";
  return "NOT ENOUGH DATA";
}

function renderToss() {
  const them = currentThem();
  const card = $("toss-card");
  card.innerHTML = "";
  if (!them) return;
  const t = them.toss;
  const pt = them.parTarget;
  card.append(
    el("div", "toss-verdict", `<span class="toss-badge ${t.recommendation}">${tossBadgeText(t.recommendation)}</span>`),
    el("div", "toss-reason", t.reason),
    el("div", "toss-split", `
      <span><b>${state.opponent}</b> batting first: ${t.battingFirst.wins}/${t.battingFirst.matches} won
      ${t.battingFirst.winPct != null ? `(${t.battingFirst.winPct}%)` : ""}, avg score
      <b>${t.battingFirst.avgScore ?? "—"}</b></span>
      <span><b>${state.opponent}</b> chasing: ${t.chasing.wins}/${t.chasing.matches} won
      ${t.chasing.winPct != null ? `(${t.chasing.winPct}%)` : ""}, avg winning chase
      <b>${t.chasing.avgChaseSuccess ?? "—"}</b></span>
    `),
  );

  const parTargetRow = el("div", "par-target-row");
  const parStat = el("div", "par-target-stat");
  parStat.append(
    el("div", "pt-label", "Par score to set — if we bat first"),
    pt.parScoreToSet.value != null
      ? el("div", "pt-value", String(pt.parScoreToSet.value))
      : el("div", "pt-value dim", "Not enough data"),
    el("div", "pt-note", pt.parScoreToSet.value != null
      ? `avg total that has beaten ${state.opponent} this season (${pt.parScoreToSet.sampleSize} losses) — aim to clear this.`
      : `${state.opponent} needs ${3 - pt.parScoreToSet.sampleSize} more loss(es) recorded before this is reliable.`),
  );
  const targetStat = el("div", "par-target-stat");
  targetStat.append(
    el("div", "pt-label", "Target to chase — if we field first"),
    pt.targetToChase.value != null
      ? el("div", "pt-value", String(pt.targetToChase.value))
      : el("div", "pt-value dim", "Not enough data"),
    el("div", "pt-note", pt.targetToChase.value != null
      ? `${state.opponent}'s avg score batting first (${pt.targetToChase.sampleSize} matches) — expect to chase around this.`
      : `${state.opponent} has batted first only ${pt.targetToChase.sampleSize} time(s) this season.`),
  );
  parTargetRow.append(parStat, targetStat);
  card.appendChild(parTargetRow);
}

/* ── Chase plan ────────────────────────────────────────────────────── */
const CHASE_SEGMENT_LABELS = ["Overs 1-4", "Overs 5-8", "Overs 9-12", "Overs 13-16"];

function renderChasePlan() {
  const them = currentThem();
  const input = $("chase-target-input");
  const box = $("chase-plan-cards");
  box.innerHTML = "";
  if (!them) return;

  // reset to this opponent's computed target only when the matchup actually changes —
  // preserves whatever the user typed if they're just re-rendering the same matchup
  if (input.dataset.opponent !== state.opponent) {
    input.dataset.opponent = state.opponent;
    const def = them.parTarget.targetToChase.value;
    input.value = def != null ? def : "";
  }

  const target = parseInt(input.value, 10);
  if (!target || target <= 0) return;

  const avgEcon = (arr) => (arr && arr.length ? arr.reduce((s, b) => s + b.econ, 0) / arr.length : null);
  const strongEcon = avgEcon(them.bowlingStrengths);
  const weakEcon = avgEcon(them.weakBowlers);

  // assume their best bowlers open and close the innings, weaker/part-time bowlers fill
  // the middle — a standard captaincy pattern — so weight each 4-over block's share of
  // the target by the expected economy rate there: tougher blocks get a smaller ask,
  // easier ones a bigger one, and the shares always sum back to the full target.
  let segEcons, usedFallback;
  if (strongEcon != null && weakEcon != null) {
    segEcons = [strongEcon, weakEcon, weakEcon, strongEcon];
    usedFallback = false;
  } else {
    segEcons = [1, 1, 1, 1];
    usedFallback = true;
  }
  const sumEcon = segEcons.reduce((a, b) => a + b, 0);
  const segTargets = segEcons.map((e) => Math.round((target * e) / sumEcon));
  const roundingDiff = target - segTargets.reduce((a, b) => a + b, 0);
  segTargets[segTargets.length - 1] += roundingDiff;

  let cumulative = 0;
  CHASE_SEGMENT_LABELS.forEach((label, i) => {
    cumulative += segTargets[i];
    const card = el("div", "chase-card");
    card.append(
      el("div", "chase-label", label),
      el("div", "chase-runs", `${segTargets[i]} runs`),
      el("div", "chase-note", `${(segTargets[i] / 4).toFixed(1)}/over · need ${cumulative} by the end of this block`),
    );
    box.appendChild(card);
  });

  if (usedFallback) {
    box.appendChild(el("div", "empty-note",
      `Not enough bowling data on ${state.opponent} yet to weight this by strength — showing an even split.`));
  }
}

/* ── Record + head-to-head ────────────────────────────────────────── */
function renderRecord() {
  const s = currentSeriesData();
  const us = currentUs(), them = currentThem();
  const grid = $("record-grid");
  grid.innerHTML = "";
  if (!us || !them) return;

  const tile = (label, usVal, themVal) => {
    const t = el("div", "compare-tile");
    t.append(el("div", "ct-label", label));
    const r1 = el("div", "ct-row");
    r1.append(el("span", "ct-team us", s.gladiators), el("span", "ct-val", usVal));
    const r2 = el("div", "ct-row");
    r2.append(el("span", "ct-team them", state.opponent), el("span", "ct-val", themVal));
    t.append(r1, r2);
    grid.appendChild(t);
  };

  const winPct = (t) => t.matches ? Math.round(100 * t.wins / t.matches) : 0;
  const standingText = (t) => t.standing
    ? `Group ${t.standing.group} · #${t.standing.rank} of ${t.standing.rankOf} · ${t.standing.pts} pts · NRR ${t.standing.netRR > 0 ? "+" : ""}${t.standing.netRR}`
    : "—";
  tile("Points table standing", standingText(us), standingText(them));
  tile("Season record", `${us.wins}-${us.losses}${us.ties ? `-${us.ties}` : ""} (${winPct(us)}%)`,
    `${them.wins}-${them.losses}${them.ties ? `-${them.ties}` : ""} (${winPct(them)}%)`);
  const homeAwayText = (t) => {
    const fmt = (side) => side.matches ? `${side.wins}-${side.matches - side.wins} (${side.winPct}%)` : "no matches yet";
    return `Home ${fmt(t.homeAway.home)} · Away ${fmt(t.homeAway.away)}`;
  };
  tile("Home / away record", homeAwayText(us), homeAwayText(them));
  tile("Runs from boundaries", `${us.boundaryDependencyPct}%`, `${them.boundaryDependencyPct}%`);
  tile("Top scorer this season", us.topBatsmen[0] ? `${us.topBatsmen[0].player} · ${us.topBatsmen[0].runs}` : "—",
    them.topBatsmen[0] ? `${them.topBatsmen[0].player} · ${them.topBatsmen[0].runs}` : "—");
  tile("Top wicket-taker this season", us.topBowlers[0] ? `${us.topBowlers[0].player} · ${us.topBowlers[0].wickets}` : "—",
    them.topBowlers[0] ? `${them.topBowlers[0].player} · ${them.topBowlers[0].wickets}` : "—");
}

/* ── Batting collapses ────────────────────────────────────────────── */
function renderCollapses() {
  const s = currentSeriesData();
  const us = currentUs(), them = currentThem();
  const row = $("collapse-row");
  row.innerHTML = "";
  if (!us || !them) return;

  const stat = (label, c) => {
    const el1 = el("div", "par-target-stat");
    const worstText = c.worst
      ? `worst: ${c.worst.wickets} wkts for ${c.worst.runs} runs vs ${c.worst.opponent}`
      : "no collapse this season";
    el1.append(
      el("div", "pt-label", label),
      el("div", "pt-value", `${c.collapsePct}%`),
      el("div", "pt-note", `${c.collapseCount} of ${c.totalInnings} innings · ${worstText}`),
    );
    row.appendChild(el1);
  };
  stat(s.gladiators, us.battingCollapses);
  stat(state.opponent, them.battingCollapses);
}

function renderH2H() {
  const s = currentSeriesData();
  const them = currentThem();
  const card = $("h2h-card");
  card.innerHTML = "";
  if (!them) return;
  const h = them.headToHead;
  card.appendChild(el("div", "h2h-record",
    `<span class="big">${h.played}</span> <span class="muted">played this season</span>` +
    (h.played ? ` &nbsp;·&nbsp; <span class="big" style="color:var(--win)">${h.wins}</span> <span class="muted">won</span>` +
      ` &nbsp;·&nbsp; <span class="big" style="color:var(--loss)">${h.losses}</span> <span class="muted">lost</span>` : "")));
  if (!h.played) {
    card.appendChild(el("div", "empty-note", `${s.gladiators} haven't played ${state.opponent} yet this season.`));
    return;
  }
  const list = el("div", "h2h-matches");
  h.matches.forEach((m) => {
    const row = el("div", "h2h-match");
    const resClass = m.result === "Win" ? "win" : m.result === "Loss" ? "loss" : "tie";
    row.append(
      el("span", null, `${s.gladiators} ${m.gladiatorsScore} ${m.battedFirst ? "(bat 1st)" : "(chased)"} vs ${state.opponent} ${m.opponentScore}`),
      el("span", `result-pill ${resClass}`, m.result),
    );
    list.appendChild(row);
  });
  card.appendChild(list);
}

/* ── Player cards ──────────────────────────────────────────────────── */
function stackBar(dismissals) {
  const wrap = el("div");
  if (!dismissals || !dismissals.total) {
    wrap.appendChild(el("div", "no-data", "No dismissal data yet."));
    return wrap;
  }
  const track = el("div", "stack-track");
  dismissals.breakdown.forEach((d) => {
    const seg = el("div", "stack-seg");
    seg.style.width = d.pct + "%";
    seg.style.background = DISMISSAL_COLORS[d.type] || "var(--grey)";
    bindTooltip(seg, `<b>${d.type}</b><br>${d.count} of ${dismissals.total} (${d.pct}%)`);
    track.appendChild(seg);
  });
  const legend = el("div", "stack-legend");
  dismissals.breakdown.forEach((d) => {
    const item = el("div", "lg-item");
    const sw = el("span", "lg-swatch");
    sw.style.background = DISMISSAL_COLORS[d.type] || "var(--grey)";
    item.append(sw, document.createTextNode(`${d.type} ${d.pct}%`));
    legend.appendChild(item);
  });
  wrap.append(track, legend);
  return wrap;
}

const FORM_BADGE = {
  hot: { text: "🔥 Hot streak", cls: "hot" },
  cold: { text: "❄️ Cold — bounce-back mode", cls: "cold" },
  steady: { text: "Steady", cls: "steady" },
};

function formStrip(recentForm) {
  const wrap = el("div", "form-strip");
  if (!recentForm || !recentForm.innings.length) {
    wrap.appendChild(el("span", "no-data", "No recent form data yet."));
    return wrap;
  }
  wrap.appendChild(el("span", "form-label", "Last 5:"));
  recentForm.innings.forEach((inn) => {
    wrap.appendChild(el("span", "form-score", `${inn.runs}${inn.notOut ? "*" : ""}`));
  });
  const badge = FORM_BADGE[recentForm.trend];
  if (badge) {
    const b = el("span", `form-badge ${badge.cls}`, badge.text);
    bindTooltip(b, `Last 5 avg <b>${recentForm.last5Mean}</b> vs season avg <b>${recentForm.seasonMean}</b>`);
    wrap.appendChild(b);
  }
  return wrap;
}

function renderBatsmenColumn(containerId, team) {
  const box = $(containerId);
  box.innerHTML = "";
  if (!team || !team.topBatsmen.length) {
    box.appendChild(el("div", "no-data", "No batting data."));
    return;
  }
  team.topBatsmen.forEach((b) => {
    const card = el("div", "player-card");
    const top = el("div", "pc-top");
    top.append(
      el("span", "pc-name", b.player),
      el("span", "pc-headline", `<strong>${b.runs}</strong> runs · avg ${b.avg} · SR ${b.sr}`),
    );
    card.append(top, el("div", "pc-meta", `${b.innings} inns · HS ${b.hs} · ${b.fours}×4s ${b.sixes}×6s`));
    card.appendChild(stackBar(b.dismissals));
    card.appendChild(formStrip(b.recentForm));
    box.appendChild(card);
  });
}

function renderBowlersColumn(containerId, team) {
  const box = $(containerId);
  box.innerHTML = "";
  if (!team || !team.topBowlers.length) {
    box.appendChild(el("div", "no-data", "No bowling data."));
    return;
  }
  team.topBowlers.forEach((b) => {
    const card = el("div", "player-card");
    const top = el("div", "pc-top");
    top.append(
      el("span", "pc-name", b.player),
      el("span", "pc-headline", `<strong>${b.wickets}</strong> wkts · econ ${b.econ}${b.avg != null ? ` · avg ${b.avg}` : ""}`),
    );
    card.append(top, el("div", "pc-meta", `${b.overs} overs · ${b.runs} runs conceded`));
    card.appendChild(stackBar(b.wicketTypes));
    box.appendChild(card);
  });
}

function renderPlayers() {
  const s = currentSeriesData();
  const us = currentUs(), them = currentThem();
  $("bat-label-us").textContent = s.gladiators;
  $("bat-label-them").textContent = state.opponent;
  $("bowl-label-us").textContent = s.gladiators;
  $("bowl-label-them").textContent = state.opponent;
  renderBatsmenColumn("bat-list-us", us);
  renderBatsmenColumn("bat-list-them", them);
  renderBowlersColumn("bowl-list-us", us);
  renderBowlersColumn("bowl-list-them", them);
}

/* ── Bowling battle: our strengths vs their weaknesses ──────────────── */
function bowlerCard(rank, positive, name, meta, statChips) {
  const card = el("div", `target-card${positive ? " positive" : ""}`);
  const rankEl = el("div", "target-rank", String(rank));
  const body = el("div", "target-body");
  const top = el("div", "target-top");
  top.append(el("span", "target-name", name), el("span", "target-meta", meta));
  const stats = el("div", "target-stats");
  statChips.forEach((html) => stats.appendChild(el("span", "target-stat", html)));
  body.append(top, stats);
  card.append(rankEl, body);
  return card;
}

function renderBowlingBattle() {
  const s = currentSeriesData();
  const us = currentUs(), them = currentThem();
  $("strength-label-us").textContent = s.gladiators;
  $("target-label-them").textContent = state.opponent;

  const strengthBox = $("strength-list-us");
  strengthBox.innerHTML = "";
  if (!us || !us.bowlingStrengths.length) {
    strengthBox.appendChild(el("div", "no-data", `Not enough bowling data for ${s.gladiators} yet (need 8+ overs bowled).`));
  } else {
    us.bowlingStrengths.forEach((b, i) => {
      strengthBox.appendChild(bowlerCard(i + 1, true, b.player, `${b.overs} overs · ${b.wickets} wkts`, [
        `econ <b>${b.econ}</b>`,
        `dot balls <b>${b.dotPct}%</b>`,
      ]));
    });
  }

  const targetBox = $("target-list-them");
  targetBox.innerHTML = "";
  if (!them || !them.weakBowlers.length) {
    targetBox.appendChild(el("div", "no-data", `Not enough bowling data for ${state.opponent} yet (need 8+ overs bowled).`));
  } else {
    them.weakBowlers.forEach((b, i) => {
      targetBox.appendChild(bowlerCard(i + 1, false, b.player, `${b.overs} overs · ${b.wickets} wkts`, [
        `econ <b>${b.econ}</b>`,
        `worst spell: <b>${b.worstSpellRuns}</b> runs off <b>${b.worstSpellBalls}</b> balls`,
        `<b>${b.extras}</b> extras (${b.extrasRate}/over)`,
      ]));
    });
  }
}

/* ── Death overs (last 3) ─────────────────────────────────────────── */
function renderDeathOvers() {
  const s = currentSeriesData();
  const box = $("death-list");
  box.innerHTML = "";
  const leaders = s.deathOversLeaders || [];
  if (!leaders.length) {
    box.appendChild(el("div", "no-data",
      `Not enough death-overs data for ${s.gladiators} yet (need 3+ overs bowled in the last 3 overs of an innings).`));
    return;
  }
  leaders.forEach((b, i) => {
    box.appendChild(bowlerCard(i + 1, true, b.player, `${b.oversBowled} death overs · ${b.runs} runs conceded`, [
      `econ <b>${b.econ}</b>/over`,
    ]));
  });
}

/* ── Other metrics ─────────────────────────────────────────────────── */
function renderMetrics() {
  const s = currentSeriesData();
  const us = currentUs(), them = currentThem();
  const grid = $("metric-grid");
  grid.innerHTML = "";
  if (!us || !them) return;

  const depend = them.topBatsmen[0]
    ? Math.round(100 * them.topBatsmen[0].runs / (them.topBatsmen.reduce((a, b) => a + b.runs, 0) || 1))
    : null;
  grid.appendChild(el("div", "metric-tile",
    `<h3>How much do they lean on ${them.topBatsmen[0]?.player ?? "their top scorer"}?</h3>
     <div style="font-size:1.6rem;font-weight:800;font-family:'Sora',sans-serif;">${depend != null ? depend + "%" : "—"}</div>
     <div class="mt-note">share of their top-3 batsmen's runs scored by their #1 — the higher this is,
     the more a match plan built around containing/removing him early pays off.</div>`));

  const wi = them.keyBatsmanWinImpact;
  const wiPlayer = them.topBatsmen[0]?.player ?? "their top scorer";
  grid.appendChild(el("div", "metric-tile",
    wi
      ? `<h3>What if we get ${wiPlayer} out early?</h3>
         <div style="font-size:1.6rem;font-weight:800;font-family:'Sora',sans-serif;">${wi.swing >= 0 ? "+" : ""}${wi.swing}pp</div>
         <div class="mt-note">${state.opponent} win <b>${wi.highWinPct}%</b> of matches (${wi.highN}) when he scores
         ${wi.threshold}+, but just <b>${wi.lowWinPct}%</b> (${wi.lowN}) when he's held under ${wi.threshold}.
         Low-score innings are the closest proxy we have for an early dismissal — no ball-by-ball timing
         for opponent teams, only runs scored.</div>`
      : `<h3>What if we get ${wiPlayer} out early?</h3>
         <div style="font-size:1.6rem;font-weight:800;font-family:'Sora',sans-serif;">—</div>
         <div class="mt-note">not enough matches yet to split his innings into a reliable high/low-score comparison.</div>`));

  grid.appendChild(el("div", "metric-tile",
    `<h3>${state.opponent} boundary dependence</h3>
     <div style="font-size:1.6rem;font-weight:800;font-family:'Sora',sans-serif;">${them.boundaryDependencyPct}%</div>
     <div class="mt-note">share of their total runs from 4s/6s (ours: ${us.boundaryDependencyPct}%). High = cut off
     boundary balls and let dot-ball pressure do the work; low = they rotate strike, so cutting singles matters more.</div>`));

  const usAtk = us.topBowlers[0], themAtk = them.topBowlers[0];
  grid.appendChild(el("div", "metric-tile",
    `<h3>Strike bowler match-up</h3>
     <div style="font-size:0.95rem;">
       <b class="gold">${s.gladiators}:</b> ${usAtk ? `${usAtk.player} — ${usAtk.wickets} wkts @ ${usAtk.econ}/over` : "—"}<br>
       <b style="color:var(--blue)">${state.opponent}:</b> ${themAtk ? `${themAtk.player} — ${themAtk.wickets} wkts @ ${themAtk.econ}/over` : "—"}
     </div>
     <div class="mt-note">whoever wins the powerplay/opening overs against the opposing strike bowler
     usually sets up the rest of the innings.</div>`));

  const h = them.headToHead;
  grid.appendChild(el("div", "metric-tile",
    `<h3>Recent history vs ${state.opponent}</h3>
     <div style="font-size:1.6rem;font-weight:800;font-family:'Sora',sans-serif;">
       ${h.played ? `${h.wins}-${h.losses}${h.ties ? `-${h.ties}` : ""}` : "First meeting"}
     </div>
     <div class="mt-note">${h.played ? "our head-to-head record this season." : "no matches played between these two teams yet this season."}</div>`));
}

/* ── Data freshness ───────────────────────────────────────────────── */
function renderDataUpdated() {
  const d = new Date(NJSBCL_DATA.generated + "T00:00:00");
  const formatted = d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  $("data-updated-badge").textContent = `Data last updated: ${formatted}`;
}

/* ── Wiring ────────────────────────────────────────────────────────── */
function updateMatchupLabel() {
  const s = currentSeriesData();
  $("matchup-us").textContent = s.gladiators;
  $("matchup-them").textContent = state.opponent;
}

function renderAll() {
  updateMatchupLabel();
  renderWinProb();
  renderFixtures();
  renderToss();
  renderChasePlan();
  renderRecord();
  renderH2H();
  renderCollapses();
  renderPlayers();
  renderBowlingBattle();
  renderDeathOvers();
  renderMetrics();
}

/* ── Side nav scrollspy ────────────────────────────────────────────── */
function initSideToc() {
  const toc = $("side-toc");
  if (!toc) return;
  const links = [...toc.querySelectorAll(".side-toc-link")];
  const sections = links
    .map((l) => document.getElementById(l.getAttribute("href").slice(1)))
    .filter(Boolean);
  const setActive = (id) => {
    links.forEach((l) => l.classList.toggle("active", l.getAttribute("href") === `#${id}`));
  };
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) setActive(entry.target.id);
      });
    },
    { rootMargin: "-15% 0px -75% 0px", threshold: 0 }
  );
  sections.forEach((s) => observer.observe(s));
  // The last section's top can never reach the rootMargin band above once the
  // page runs out of room to scroll further, so it'd otherwise stay stuck on
  // whichever section was active before — force it once we hit true bottom.
  window.addEventListener("scroll", () => {
    const atBottom = window.innerHeight + window.scrollY >= document.body.scrollHeight - 4;
    if (atBottom && sections.length) setActive(sections[sections.length - 1].id);
  }, { passive: true });
}

renderDataUpdated();
buildSeriesPills();
populateOpponentSelect();
initSideToc();
$("opponent-select").addEventListener("change", (e) => {
  state.opponent = e.target.value;
  renderAll();
});
$("fixtures-toggle").addEventListener("click", () => {
  state.showAllFixtures = !state.showAllFixtures;
  renderFixtures();
});
$("chase-target-input").addEventListener("input", renderChasePlan);
renderAll();
