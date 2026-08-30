/* NJSBCL Scout — Last match recap (reads the same NJSBCL_DATA as app.js/charts.js). */
"use strict";

const $ = (id) => document.getElementById(id);
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
};

function fmtScore(z) { return z >= 0 ? `+${z.toFixed(2)}` : z.toFixed(2); }

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

/* ── Recap ─────────────────────────────────────────────────────────── */
function verdictCard(rank, positive, v) {
  const card = el("div", `ai-insight-card ${positive ? "positive" : "negative"}`);
  card.append(
    el("div", "ai-insight-rank", String(rank)),
    el("div", "ai-insight-title", v.title),
    el("div", "ai-insight-detail", v.detail),
  );
  return card;
}

function renderMatchRecap() {
  const s = currentSeriesData();
  const box = $("recap-content");
  box.innerHTML = "";
  const recap = s.matchRecap;
  if (!recap) {
    box.appendChild(el("div", "empty-note", `No completed matches yet for ${s.gladiators} this season.`));
    return;
  }

  const resultColor = recap.result === "Win" ? "var(--win)" : recap.result === "Loss" ? "var(--loss)" : "var(--muted)";
  const header = el("div", "recap-header");
  header.innerHTML = `<span class="gold" style="font-weight:700;">${s.gladiators}</span> ${recap.gladiatorsScore}
    vs <span style="color:var(--blue);font-weight:700;">${recap.opponent}</span> ${recap.opponentScore}
    — <b style="color:${resultColor}">${recap.result}</b>
    (${recap.battedFirst ? s.gladiators : recap.opponent} batted first)
    ${recap.date ? `<span class="recap-date">${recap.date}</span>` : ""}`;
  box.appendChild(header);

  if (recap.starOfMatch) {
    const star = recap.starOfMatch;
    // On anything other than a win, keep the player and score but drop the celebratory
    // framing: a gold "Star of the match" banner sitting directly under a red "Loss" reads
    // as celebrating the defeat. The performance is still worth surfacing — every loss this
    // season still had a clearly positive standout — so this relabels rather than hides.
    const won = recap.result === "Win";
    const card = el("div", "star-card" + (won ? "" : " muted"));
    const body = el("div");
    body.innerHTML = `<div class="star-badge">${won ? "Star of the match" : "Top performer"}</div>
      <div class="star-name">${star.player}</div>
      <div class="star-lines">${[star.battingLine, star.bowlingLine].filter(Boolean).join(" &middot; ")}</div>`;
    const pts = el("div", "star-points");
    pts.innerHTML = `<div class="num">${fmtScore(star.impactScore)}</div><div class="label">impact score</div>`;
    card.append(body, pts);
    box.appendChild(card);
  }

  const columns = el("div", "recap-columns");
  const rightCol = el("div", "recap-col right");
  rightCol.appendChild(el("h3", null, "What we got right"));
  if (!recap.right.length) rightCol.appendChild(el("div", "empty-note", "No clear-cut hits this match."));
  recap.right.forEach((r, i) => rightCol.appendChild(verdictCard(i + 1, true, r)));

  const wrongCol = el("div", "recap-col wrong");
  wrongCol.appendChild(el("h3", null, "What we got wrong"));
  if (!recap.wrong.length) wrongCol.appendChild(el("div", "empty-note", "No clear misses this match."));
  recap.wrong.forEach((r, i) => wrongCol.appendChild(verdictCard(i + 1, false, r)));

  columns.append(rightCol, wrongCol);
  box.appendChild(columns);

  if (recap.insightFollowthrough && recap.insightFollowthrough.length) {
    const wrap = el("div", "followthrough-wrap");
    wrap.appendChild(el("h3", null, "AI insight follow-through"));
    wrap.appendChild(el("p", "doc-note", "Did we act on this season's AI insights, and what "
      + "happened? Kept separate from right/wrong above since the outcome here is often mixed "
      + "— the correct call and a bad individual result aren't mutually exclusive."));
    const list = el("div", "ai-insights-list");
    recap.insightFollowthrough.forEach((f, i) => {
      const card = el("div", `ai-insight-card${f.actionable ? "" : " dim"}`);
      card.append(
        el("div", "ai-insight-rank", String(i + 1)),
        el("div", "ai-insight-title", f.title),
        el("div", "ai-insight-detail", f.detail),
      );
      list.appendChild(card);
    });
    wrap.appendChild(list);
    box.appendChild(wrap);
  }

  if (recap.pointsTable && recap.pointsTable.length) {
    const wrap = el("div", "points-table-wrap");
    wrap.appendChild(el("h3", null, "Full match impact scores"));
    wrap.appendChild(el("p", "doc-note", "Batting and bowling points are each z-scored against "
      + "every batting/bowling performance in the league this season, then summed — so a good "
      + "bowling spell doesn't automatically outrank a good knock just because wickets carry "
      + "more raw points than runs. Each impact column is how many standard deviations above "
      + "(or below) the league average that discipline was; <b>Total</b> is the two added "
      + "together. A dash means they didn't bat or bowl at all, which is different from 0.00 "
      + "(exactly league average)."));
    const table = document.createElement("table");
    table.className = "points-table";
    const thead = el("thead");
    const headRow = el("tr");
    // Show the two z-scores that make up the total, not just the total: the whole point of
    // z-scoring each discipline separately is that a bowling spell and a knock become
    // comparable, and you can only see that happening if both halves are on screen.
    ["Player", "Batting", "Bat impact", "Bowling", "Bowl impact", "Total"]
      .forEach((h) => headRow.appendChild(el("th", null, h)));
    thead.appendChild(headRow);
    table.appendChild(thead);
    const tbody = el("tbody");
    recap.pointsTable.forEach((r) => {
      const row = el("tr");
      row.appendChild(el("td", null, r.player));
      row.appendChild(el("td", null, r.battingLine || "—"));
      // A null z-score means they didn't bat/bowl at all — distinct from a genuine 0.00,
      // which would mean they performed exactly at the league average.
      row.appendChild(el("td", "num sub", r.battingZ == null ? "—" : fmtScore(r.battingZ)));
      row.appendChild(el("td", null, r.bowlingLine || "—"));
      row.appendChild(el("td", "num sub", r.bowlingZ == null ? "—" : fmtScore(r.bowlingZ)));
      row.appendChild(el("td", "num", fmtScore(r.impactScore)));
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    box.appendChild(wrap);
  }
}

/* ── Wiring ────────────────────────────────────────────────────────── */
function renderAll() {
  renderMatchRecap();
}

renderDataUpdated();
buildSeriesPills();
renderAll();
