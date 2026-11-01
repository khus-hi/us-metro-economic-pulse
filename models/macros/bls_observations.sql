{#
  Flattens BLS API responses: file -> Results.series[] -> data[] -> one row per
  series per period. Keeps monthly periods (M01-M12; M13 is the annual average),
  and the latest run if a series was pulled more than once.
#}
{% macro bls_observations(source_relation) %}
with files as (
    select filename, content::json as j, {{ run_date_from('filename') }} as run_date
    from {{ source_relation }}
),
series as (
    select run_date, unnest(from_json(j -> '$.Results.series', '["json"]')) as s
    from files
),
obs as (
    select
        run_date,
        trim(s ->> 'seriesID') as series_id,
        unnest(from_json(s -> '$.data', '["json"]')) as d
    from series
),
typed as (
    select
        series_id,
        cast(d ->> 'year' as integer) as year,
        d ->> 'period' as period,
        try_cast(d ->> 'value' as double) as value,
        coalesce(cast(d -> '$.footnotes' as varchar), '') like '%"code":"P"%' as is_preliminary,
        run_date
    from obs
)
select
    series_id,
    make_date(year, cast(substr(period, 2) as integer), 1) as month_date,
    value,
    is_preliminary,
    run_date
from typed
where period between 'M01' and 'M12'
qualify row_number() over (partition by series_id, year, period order by run_date desc) = 1
{% endmacro %}
