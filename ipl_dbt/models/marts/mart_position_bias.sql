-- Analysis B & C: balls faced and powerplay run% aggregated by position group.
-- Minimum 7 matches to qualify (avoids small-sample noise).
select
    position_group,
    count(*)                            as batter_seasons,
    round(avg(balls_faced), 1)          as avg_balls_faced,
    round(median(balls_faced), 1)       as median_balls_faced,
    round(avg(runs), 1)                 as avg_runs,
    round(median(runs), 1)              as median_runs,
    round(avg(pp_pct), 1)               as avg_pp_pct,
    round(median(pp_pct), 1)            as median_pp_pct
from {{ ref('int_batter_season') }}
where matches >= 7
group by position_group
