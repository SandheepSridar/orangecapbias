-- Middle-Order Value Index (MOVI): equal-weighted z-score composite of
-- volume, efficiency, finishing, and consistency for middle-order batsmen
-- (avg_pos 4–7, 7+ matches), scored within each season.
-- Replicates src/middle_order_index.py in SQL.
with legal as (
    select *
    from {{ ref('stg_ball_by_ball') }}
    where extras_type != 'wide'
),

-- per-match runs → mean_rpi and median_rpi
match_runs as (
    select
        season,
        batter,
        match_id,
        sum(runs_batter) as match_runs
    from {{ ref('stg_ball_by_ball') }}
    group by season, batter, match_id
),

innings_stats as (
    select
        season,
        batter,
        count(match_id)     as innings_count,
        avg(match_runs)     as mean_rpi,
        median(match_runs)  as median_rpi
    from match_runs
    group by season, batter
),

-- death-over SR (legal balls only)
death_sr as (
    select
        season,
        batter,
        sum(runs_batter) * 100.0 / count(*) as death_strike_rate
    from legal
    where phase = 'death'
    group by season, batter
),

base as (
    select
        season,
        batter,
        count(*)                            as balls_faced,
        sum(runs_batter)                    as runs,
        avg(batting_position)               as avg_pos,
        count(distinct match_id)            as matches,
        sum(runs_batter) * 100.0 / count(*) as strike_rate
    from legal
    group by season, batter
),

combined as (
    select
        b.season,
        b.batter,
        b.balls_faced,
        b.runs,
        b.avg_pos,
        b.matches,
        b.strike_rate,
        i.innings_count,
        i.mean_rpi,
        i.median_rpi,
        d.death_strike_rate
    from base b
    left join innings_stats i using (season, batter)
    left join death_sr      d using (season, batter)
    where b.avg_pos >= 4
      and b.avg_pos <= 7
      and b.matches >= 7
),

-- players with no death balls get the season-mean death SR so their z_finishing = 0
season_death_mean as (
    select season, avg(death_strike_rate) as mean_death_sr
    from combined
    group by season
),

with_death_filled as (
    select
        c.*,
        coalesce(c.death_strike_rate, s.mean_death_sr) as death_sr_filled
    from combined c
    left join season_death_mean s using (season)
),

-- compute season-level mean and stddev for each component (ddof=1 = stddev_samp)
season_stats as (
    select
        season,
        avg(mean_rpi)        as mu_volume,      stddev_samp(mean_rpi)        as sd_volume,
        avg(strike_rate)     as mu_efficiency,  stddev_samp(strike_rate)     as sd_efficiency,
        avg(death_sr_filled) as mu_finishing,   stddev_samp(death_sr_filled) as sd_finishing,
        avg(median_rpi)      as mu_consistency, stddev_samp(median_rpi)      as sd_consistency
    from with_death_filled
    group by season
),

zscored as (
    select
        w.*,
        (w.mean_rpi        - s.mu_volume)      / nullif(s.sd_volume,       0) as z_volume,
        (w.strike_rate     - s.mu_efficiency)  / nullif(s.sd_efficiency,   0) as z_efficiency,
        (w.death_sr_filled - s.mu_finishing)   / nullif(s.sd_finishing,    0) as z_finishing,
        (w.median_rpi      - s.mu_consistency) / nullif(s.sd_consistency,  0) as z_consistency
    from with_death_filled w
    join season_stats s using (season)
),

scored as (
    select
        *,
        -- coalesce mirrors Python's mean(skipna=True): z=0 when stddev is null (n=1 season)
        (coalesce(z_volume, 0) + coalesce(z_efficiency, 0)
            + coalesce(z_finishing, 0) + coalesce(z_consistency, 0)) / 4.0 as movi_score
    from zscored
)

select
    season,
    batter,
    matches,
    innings_count,
    round(avg_pos, 2)           as avg_pos,
    runs,
    balls_faced,
    round(mean_rpi, 1)          as mean_rpi,
    round(median_rpi, 1)        as median_rpi,
    round(strike_rate, 1)       as strike_rate,
    round(death_strike_rate, 1) as death_sr,
    round(z_volume, 2)          as z_volume,
    round(z_efficiency, 2)      as z_efficiency,
    round(z_finishing, 2)       as z_finishing,
    round(z_consistency, 2)     as z_consistency,
    round(movi_score, 2)        as movi_score,
    rank() over (partition by season order by movi_score desc) as season_rank
from scored
order by season, season_rank
