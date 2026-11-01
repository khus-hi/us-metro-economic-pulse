{{ config(materialized='view', schema='staging') }}
-- ACS 2024 5-year, one row per CBSA x variable, with the margin of error beside the estimate.
-- Raw files are "list of lists": the first row is the header. Works for both the API
-- and the Summary File route because ingest writes both in the same shape.
-- Census annotation codes (e.g. -555555555) are not numbers: they become NULL here,
-- and the code is kept in *_annotation so we know why.
with files as (
    select from_json(content::json, '[["varchar"]]') as rows_, {{ run_date_from('filename') }} as run_date
    from {{ source('raw', 'census_acs') }}
),
r as (
    select run_date, rows_[1] as header, unnest(rows_[2:]) as row_ from files
),
cells as (
    select
        run_date,
        row_[list_position(header, 'metropolitan statistical area/micropolitan statistical area')] as cbsa_code,
        header[i] as col,
        row_[i] as raw_value
    from (select *, unnest(range(1, len(header) + 1)) as i from r)
    where regexp_matches(header[i], '^B\d+[A-Z]?_\d{3}[EM]$')
),
latest as (
    select * from cells
    qualify row_number() over (partition by cbsa_code, col order by run_date desc) = 1
),
annotated as (
    select
        l.cbsa_code,
        left(l.col, length(l.col) - 1) as variable,
        right(l.col, 1) as kind,
        case when a.code is null then try_cast(l.raw_value as double) end as value,
        a.code as annotation,
        l.run_date
    from latest l
    left join {{ ref('census_annotations') }} a on trim(l.raw_value) = a.code
)
select
    cbsa_code,
    variable,
    max(case when kind = 'E' then value end) as estimate,
    max(case when kind = 'M' then value end) as moe,
    max(case when kind = 'E' then annotation end) as estimate_annotation,
    max(case when kind = 'M' then annotation end) as moe_annotation,
    {{ var('acs_year') }} as acs_year,
    '{{ var("acs_vintage") }}' as acs_vintage,
    max(run_date) as run_date
from annotated
group by cbsa_code, variable
