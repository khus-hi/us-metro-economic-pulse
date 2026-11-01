{{ config(materialized='view', schema='staging') }}
-- OEWS May 2025, top-50 metros x analyst occupations (+ 00-0000 all occupations).
-- OEWS special symbols: '*' / '**' = not available, '#' = wage is at or above the
-- top-code limit. Those become NULL, and '#' sets a top-coded flag so a reader knows
-- the true value is higher, not missing.
{% set money = ['A_MEAN', 'A_PCT10', 'A_PCT25', 'A_MEDIAN', 'A_PCT75', 'A_PCT90', 'H_MEAN', 'H_MEDIAN'] %}
with src as (
    select *, {{ run_date_from('filename') }} as run_date
    from {{ source('raw', 'oews') }}
    qualify row_number() over (partition by AREA, OCC_CODE order by run_date desc) = 1
)
select
    lpad(trim(AREA), 5, '0') as cbsa_code,
    AREA_TITLE as area_title,
    OCC_CODE as soc_code,
    OCC_TITLE as occupation_title,
    try_cast(replace(TOT_EMP, ',', '') as double) as employment,
    try_cast(JOBS_1000 as double) as jobs_per_1000,
    try_cast(LOC_QUOTIENT as double) as location_quotient,
    {% for c in money -%}
    try_cast(replace({{ c }}, ',', '') as double) as {{ c | lower }},
    {% endfor -%}
    (A_PCT90 = '#' or A_MEDIAN = '#' or A_MEAN = '#') as is_top_coded,
    {{ var('oews_year') }} as oews_year,
    run_date
from src
