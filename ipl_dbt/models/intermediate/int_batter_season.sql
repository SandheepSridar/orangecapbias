-- One row per batter per season.
-- balls_faced = legal balls only (wides excluded), matching IPL official convention.
with legal as (
    select *
    from {{ ref('stg_ball_by_ball') }}
    where extras_type != 'wide'
),

agg as (
    select
        season,
        batter,
        count(*)                                                                as balls_faced,
        sum(runs_batter)                                                        as runs,
        avg(batting_position)                                                   as avg_pos,
        count(distinct match_id)                                                as matches,
        max(case when match_stage != 'league' then 1 else 0 end)               as made_playoffs,
        sum(case when phase = 'powerplay' then runs_batter else 0 end)         as pp_runs,
        sum(case when phase = 'middle'    then runs_batter else 0 end)         as middle_runs,
        sum(case when phase = 'death'     then runs_batter else 0 end)         as death_runs
    from legal
    group by season, batter
)

select
    *,
    {{ position_group('avg_pos') }}                                             as position_group,
    case
        when runs = 0 then null
        else round(pp_runs * 100.0 / runs, 2)
    end                                                                         as pp_pct
from agg
