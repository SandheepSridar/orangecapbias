/* Finds the single soonest upcoming match across both series in data.js and dumps
 * everything the PDF scouting report needs (our team, the opponent, our squad-wide
 * charts) to report_data.json. Run from NJSBCL/dashboard/report/:
 *   node extract_report_data.js
 */
"use strict";

const fs = require("fs");
const path = require("path");

const DATA_JS = path.join(__dirname, "..", "data.js");
const OUT = path.join(__dirname, "report_data.json");

const src = fs.readFileSync(DATA_JS, "utf8").split("\n").slice(1).join("\n");
const NJSBCL_DATA = new Function(src + "; return NJSBCL_DATA;")();

// "Sun, Aug 16 2026" -> Date
const parseFixtureDate = (s) => new Date(s.replace(/^\w+,\s*/, ""));

let best = null; // { seriesKey, fixture, dateObj }
for (const [seriesKey, s] of Object.entries(NJSBCL_DATA.series)) {
  if (!s.upcoming.length) continue;
  const fixture = s.upcoming[0];
  const dateObj = parseFixtureDate(fixture.date);
  if (!best || dateObj < best.dateObj) {
    best = { seriesKey, fixture, dateObj };
  }
}

if (!best) {
  console.error("No upcoming fixtures found in either series — nothing to report on.");
  process.exit(1);
}

const s = NJSBCL_DATA.series[best.seriesKey];
const opponent = best.fixture.opponent;
const us = s.teams[s.gladiators];
const them = s.teams[opponent];

if (!them) {
  console.error(`Opponent "${opponent}" from the fixture list has no team data in data.js.`);
  process.exit(1);
}

const payload = {
  generated: NJSBCL_DATA.generated,
  seriesLabel: s.label,
  gladiators: s.gladiators,
  opponent,
  fixture: best.fixture,
  us,
  them,
  gladiatorsCharts: {
    winDependency: s.gladiatorsCharts.winDependency,
    bestXI: s.gladiatorsCharts.bestXI,
  },
  deathOversLeaders: s.deathOversLeaders,
};

fs.writeFileSync(OUT, JSON.stringify(payload, null, 2));
console.log(`Wrote ${OUT}`);
console.log(`Next match: ${s.gladiators} vs ${opponent} — ${best.fixture.date} ${best.fixture.time} (${s.label})`);
