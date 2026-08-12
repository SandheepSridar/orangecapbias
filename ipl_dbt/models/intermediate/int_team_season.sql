-- One row per team per season with match count and playoff flag.
select
    season,
    batting_team                                                            as team,
    count(distinct match_id)                                                as matches,
    max(case when match_stage != 'league' then 1 else 0 end)               as made_playoffs
from {{ ref('stg_ball_by_ball') }}
group by season, batting_team
