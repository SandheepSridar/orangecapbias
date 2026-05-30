-- IPL Orange Cap Bias — Core Analysis Queries
-- Run against: ipl_research.bbb_clean (2008–2025, innings 1–2 only)
-- See CLAUDE.md for methodology and variable definitions

-- ── Setup ─────────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW ipl_research.bbb_clean AS
SELECT * FROM ipl_research.ball_by_ball
WHERE season <= 2025
  AND innings IN (1, 2);


-- ── Analysis A: Orange Cap Winner Batting Position (2008–2025) ────────────────
-- Claim: ~90%+ of winners batted at positions 1–3

SELECT
  season,
  winner,
  team,
  total_runs,
  matches_played,
  avg_batting_position,
  CASE
    WHEN avg_batting_position <= 2 THEN 'Opener (1-2)'
    WHEN avg_batting_position <= 3 THEN 'Top Order (3)'
    WHEN avg_batting_position <= 5 THEN 'Middle Order (4-5)'
    ELSE 'Finisher (6+)'
  END AS position_group,
  playoff_team
FROM ipl_research.orange_cap_winners
ORDER BY season;


-- ── Analysis B: Balls Faced per Season by Position Group ─────────────────────
-- Claim: Openers face significantly more balls than middle-order batsmen

WITH batter_season AS (
  SELECT
    season,
    batter,
    AVG(batting_position)  AS avg_pos,
    COUNT(*)               AS balls_faced,
    SUM(runs_batter)       AS runs
  FROM ipl_research.bbb_clean
  GROUP BY season, batter
),
grouped AS (
  SELECT *,
    CASE
      WHEN avg_pos <= 2 THEN 'Opener (1-2)'
      WHEN avg_pos <= 3 THEN 'Top Order (3)'
      WHEN avg_pos <= 5 THEN 'Middle Order (4-5)'
      ELSE 'Finisher (6+)'
    END AS position_group
  FROM batter_season
)
SELECT
  position_group,
  COUNT(*)                              AS batter_seasons,
  ROUND(AVG(balls_faced), 1)            AS avg_balls,
  ROUND(PERCENTILE(balls_faced, 0.5), 1) AS median_balls,
  MIN(balls_faced)                      AS min_balls,
  MAX(balls_faced)                      AS max_balls,
  ROUND(AVG(runs), 1)                   AS avg_runs
FROM grouped
GROUP BY position_group
ORDER BY MIN(avg_pos);


-- ── Analysis C: Powerplay Run Concentration by Position Group ─────────────────
-- Claim: Openers score 30–50% of their runs in the powerplay; middle order ~0–5%

WITH batter_phase AS (
  SELECT
    CASE
      WHEN AVG(batting_position) OVER (PARTITION BY season, batter) <= 2 THEN 'Opener (1-2)'
      WHEN AVG(batting_position) OVER (PARTITION BY season, batter) <= 3 THEN 'Top Order (3)'
      WHEN AVG(batting_position) OVER (PARTITION BY season, batter) <= 5 THEN 'Middle Order (4-5)'
      ELSE 'Finisher (6+)'
    END AS position_group,
    phase,
    runs_batter
  FROM ipl_research.bbb_clean
)
SELECT
  position_group,
  SUM(CASE WHEN phase = 'powerplay' THEN runs_batter ELSE 0 END) AS pp_runs,
  SUM(CASE WHEN phase = 'middle'    THEN runs_batter ELSE 0 END) AS mid_runs,
  SUM(CASE WHEN phase = 'death'     THEN runs_batter ELSE 0 END) AS death_runs,
  SUM(runs_batter)                                                AS total_runs,
  ROUND(SUM(CASE WHEN phase = 'powerplay' THEN runs_batter ELSE 0 END) * 100.0 / SUM(runs_batter), 1) AS pp_pct,
  ROUND(SUM(CASE WHEN phase = 'middle'    THEN runs_batter ELSE 0 END) * 100.0 / SUM(runs_batter), 1) AS mid_pct,
  ROUND(SUM(CASE WHEN phase = 'death'     THEN runs_batter ELSE 0 END) * 100.0 / SUM(runs_batter), 1) AS death_pct
FROM batter_phase
GROUP BY position_group
ORDER BY MIN(CASE position_group
  WHEN 'Opener (1-2)'      THEN 1
  WHEN 'Top Order (3)'     THEN 2
  WHEN 'Middle Order (4-5)' THEN 3
  ELSE 4
END);


-- ── Analysis D: Normalised Rankings (14-match league stage) ───────────────────
-- Claim: Normalising for matches played changes rankings in several seasons

WITH league_only AS (
  SELECT * FROM ipl_research.bbb_clean
  WHERE match_stage = 'league'
),
batter_season AS (
  SELECT
    season,
    batter,
    COUNT(DISTINCT match_id) AS league_matches,
    SUM(runs_batter)         AS league_runs,
    AVG(batting_position)    AS avg_pos
  FROM league_only
  GROUP BY season, batter
  HAVING COUNT(DISTINCT match_id) >= 7
),
with_norm AS (
  SELECT *,
    ROUND(league_runs * 14.0 / league_matches, 1)                                        AS normalised_runs,
    RANK() OVER (PARTITION BY season ORDER BY league_runs DESC)                           AS actual_rank,
    RANK() OVER (PARTITION BY season ORDER BY league_runs * 14.0 / league_matches DESC)  AS norm_rank
  FROM batter_season
)
SELECT
  season,
  batter,
  league_matches,
  league_runs,
  normalised_runs,
  actual_rank,
  norm_rank,
  ROUND(avg_pos, 1) AS avg_pos
FROM with_norm
WHERE actual_rank <= 10 OR norm_rank <= 10
ORDER BY season, actual_rank;


-- ── Analysis E: Playoff Match Advantage ───────────────────────────────────────
-- Claim: Playoff teams play ~2–3 more matches, giving a structural run advantage

WITH team_season AS (
  SELECT
    season,
    batting_team,
    COUNT(DISTINCT match_id)                                          AS matches_played,
    MAX(CASE WHEN match_stage != 'league' THEN 1 ELSE 0 END)         AS made_playoffs
  FROM ipl_research.bbb_clean
  GROUP BY season, batting_team
)
SELECT
  season,
  batting_team,
  matches_played,
  made_playoffs
FROM team_season
ORDER BY season, made_playoffs DESC, matches_played DESC;

-- Summary version: avg matches by playoff status
WITH team_season AS (
  SELECT
    season,
    batting_team,
    COUNT(DISTINCT match_id)                                    AS matches_played,
    MAX(CASE WHEN match_stage != 'league' THEN 1 ELSE 0 END)   AS made_playoffs
  FROM ipl_research.bbb_clean
  GROUP BY season, batting_team
)
SELECT
  made_playoffs,
  ROUND(AVG(matches_played), 1) AS avg_matches,
  MIN(matches_played)           AS min_matches,
  MAX(matches_played)           AS max_matches,
  COUNT(*)                      AS team_seasons
FROM team_season
GROUP BY made_playoffs
ORDER BY made_playoffs;


-- ── Analysis F: Non-Playoff Elite Batsmen ─────────────────────────────────────
-- Claim: Elite non-playoff batsmen are systematically underrepresented due to fewer matches

WITH batter_season AS (
  SELECT
    season,
    batter,
    batting_team,
    COUNT(DISTINCT match_id)                                         AS matches,
    SUM(runs_batter)                                                 AS runs,
    AVG(batting_position)                                            AS avg_pos,
    MAX(CASE WHEN match_stage != 'league' THEN 1 ELSE 0 END)        AS made_playoffs
  FROM ipl_research.bbb_clean
  GROUP BY season, batter, batting_team
  HAVING COUNT(DISTINCT match_id) >= 7
),
ranked AS (
  SELECT *,
    RANK() OVER (PARTITION BY season ORDER BY runs DESC) AS season_rank
  FROM batter_season
)
SELECT
  season,
  batter,
  batting_team,
  matches,
  runs,
  ROUND(avg_pos, 1)              AS avg_pos,
  season_rank,
  made_playoffs,
  ROUND(runs * 1.0 / matches, 1) AS runs_per_match,
  ROUND(runs * 16.0 / matches, 1) AS proj_runs_16_matches
FROM ranked
WHERE season_rank <= 5
  AND made_playoffs = 0
ORDER BY season, season_rank;
