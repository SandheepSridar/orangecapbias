/* NJSBCL Scout — "Star of the tournament" ticker, shared across every page except
   methodology.html/changelog.html. Top 3 players per series (by season-total z-scored impact
   score, see build_data.py's season_star_leaderboard), rendered as a horizontal
   auto-scrolling strip like a stock ticker / news-headline crawl. Reads the same NJSBCL_DATA
   global as the rest of the dashboard. Wrapped in an IIFE so it doesn't collide with each
   page's own $/el helpers. */
(function () {
  "use strict";

  const SERIES_LABEL = { division1: "Div1", weekenders: "Weekenders" };

  function fmtScore(z) { return (z >= 0 ? "+" : "") + z.toFixed(2); }

  function collectData() {
    const out = [];
    Object.keys(NJSBCL_DATA.series).forEach((key) => {
      const label = SERIES_LABEL[key] || key;
      const rows = (NJSBCL_DATA.series[key].gladiatorsCharts.starLeaderboard || []).slice(0, 3);
      rows.forEach((r, i) => out.push({ label, rank: i + 1, player: r.player, impact: r.totalImpact }));
    });
    return out;
  }

  function buildItem(d) {
    const item = document.createElement("span");
    item.className = "ticker-item" + (d.rank === 1 ? " ti-leader" : "");
    item.innerHTML = `<span class="ti-series">${d.label}</span><span class="ti-rank">#${d.rank}</span>` +
      `<span class="ti-player">${d.player}</span><span class="ti-impact">${fmtScore(d.impact)}</span>`;
    return item;
  }

  function buildSep() {
    const sep = document.createElement("span");
    sep.className = "ticker-sep";
    sep.textContent = "•";
    return sep;
  }

  function render() {
    const track = document.getElementById("ticker-track");
    if (!track || typeof NJSBCL_DATA === "undefined") return;
    const data = collectData();
    if (!data.length) return;
    track.innerHTML = "";
    // The item sequence is built twice so the loop-back to translateX(-50%) is seamless.
    for (let pass = 0; pass < 2; pass++) {
      data.forEach((d) => {
        track.appendChild(buildItem(d));
        track.appendChild(buildSep());
      });
    }
    requestAnimationFrame(() => {
      const singleSetWidth = track.scrollWidth / 2;
      const pxPerSecond = 40;
      track.style.animationDuration = `${Math.max(8, singleSetWidth / pxPerSecond)}s`;
    });
  }

  render();
})();
