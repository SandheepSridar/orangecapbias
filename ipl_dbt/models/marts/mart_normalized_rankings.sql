-- Analysis D: top-10 run-scorers per season with normalised run projections.
-- Non-playoff players are projected up to a 14-match season; playoff players are not.
-- 95% CI on the projection = 1.96 * stddev(match_runs) * sqrt(missing_matches).
with league as (
    select *
    from {{ ref('stg_ball_by_ball') }}
    where match_stage = 'league'
),

match_runs as (
    select
        season,
        batter,
        match_id,
        sum(runs_batter)    as match_runs
    from league
    group by season, batter, match_id
),

league_agg as (
    select
        season,
        batter,
        count(distinct match_id)    as league_matches,
        sum(match_runs)             as league_runs,
        stddev_samp(match_runs)     as runs_std
    from match_runs
    group by season, batter
),

avg_pos as (
    select
        season,
        batter,
        avg(batting_position)       as avg_pos
    from league
    group by season, batter
),

playoff_flag as (
    select
        season,
        batter,
        max(case when match_stage != 'league' then 1 else 0 end) as made_playoffs
    from {{ ref('stg_ball_by_ball') }}
    group by season, batter
),

base as (
    select
        la.season,
        la.batter,
        la.league_matches,
        la.league_runs,
        la.runs_std,
        ap.avg_pos,
        coalesce(pf.made_playoffs, 0)   as made_playoffs
    from league_agg la
    left join avg_pos ap     using (season, batter)
    left join playoff_flag pf using (season, batter)
    where la.league_matches >= 7
),

season_max as (
    select season, max(league_matches) as season_league_length
    from base
    group by season
),

normalized as (
    select
        b.*,
        sm.season_league_length,
        -- playoff players scale relative to the season league length they played;
        -- non-playoff players are projected up to a full 14-match season
        case
            when b.made_playoffs = 1 then sm.season_league_length
            else b.league_matches
        end                                                     as denom,
        case
            when b.made_playoffs = 0
            then greatest(14 - b.league_matches, 0)
            else 0
        end                                                     as missing_matches
    from base b
    join season_max sm using (season)
),

with_norm as (
    select
        *,
        league_runs * 14.0 / denom                              as norm_runs,
        1.96 * runs_std * sqrt(missing_matches)                 as ci_half
    from normalized
),

ranked as (
    select
        *,
        rank() over (partition by season order by league_runs desc) as actual_rank,
        rank() over (partition by season order by norm_runs   desc) as norm_rank
    from with_norm
)

select
    season,
    batter,
    league_matches,
    league_runs,
    round(norm_runs, 1)                             as normalised_runs,
    actual_rank,
    norm_rank,
    round(avg_pos, 1)                               as avg_pos,
    made_playoffs,
    missing_matches,
    round(greatest(norm_runs - ci_half, 0), 1)     as ci_lower,
    round(norm_runs + ci_half, 1)                  as ci_upper
from ranked
where actual_rank <= 10
order by season, actual_rank
