-- Filter to innings 1 & 2; super overs excluded at parse time
select *
from {{ source('raw', 'ball_by_ball') }}
where innings in (1, 2)
