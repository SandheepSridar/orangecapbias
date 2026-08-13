/* Writes one report_data_<seriesKey>.json per series that has an upcoming fixture
 * (both Division 1 and Weekenders Cup, normally) — everything the PDF scouting
 * report needs (our team, the opponent, our squad-wide charts) for that series'
 * next match. Run from NJSBCL/dashboard/report/:
 *   node extract_report_data.js
 */
"use strict";

const fs = require("fs");
const path = require("path");

const DATA_JS = path.join(__dirname, "..", "data.js");

const src = fs.readFileSync(DATA_JS, "utf8").split("\n").slice(1).join("\n");
const NJSBCL_DATA = new Function(src + "; return NJSBCL_DATA;")();

let wrote = 0;
for (const [seriesKey, s] of Object.entries(NJSBCL_DATA.series)) {
  if (!s.upcoming.length) {
    console.log(`${s.label}: no upcoming fixtures — skipped.`);
    continue;
  }
  const fixture = s.upcoming[0];
  const opponent = fixture.opponent;
  const us = s.teams[s.gladiators];
  const them = s.teams[opponent];
  if (!them) {
    console.error(`${s.label}: opponent "${opponent}" from the fixture list has no team data in data.js — skipped.`);
    continue;
  }

  const payload = {
    generated: NJSBCL_DATA.generated,
    seriesKey,
    seriesLabel: s.label,
    gladiators: s.gladiators,
    opponent,
    fixture,
    us,
    them,
    gladiatorsCharts: {
      winDependency: s.gladiatorsCharts.winDependency,
      bestXI: s.gladiatorsCharts.bestXI,
    },
    deathOversLeaders: s.deathOversLeaders,
  };

  const out = path.join(__dirname, `report_data_${seriesKey}.json`);
  fs.writeFileSync(out, JSON.stringify(payload, null, 2));
  console.log(`Wrote ${out}`);
  console.log(`  ${s.label}: ${s.gladiators} vs ${opponent} — ${fixture.date} ${fixture.time}`);
  wrote++;
}

if (!wrote) {
  console.error("No upcoming fixtures found in any series — nothing to report on.");
  process.exit(1);
}
