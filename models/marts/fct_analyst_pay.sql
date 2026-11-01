{{ config(materialized='table', schema='marts') }}
-- Grain: one row per metro per analyst occupation (OEWS May 2025).
-- pay_vs_all_occupations compares the occupation's median annual wage with the
-- median for all occupations in the same metro (1.5 = 50% above the local median).
with o as (select * from {{ ref('stg_oews__msa') }}),
all_occ as (
    select cbsa_code, a_median as all_occupations_median
    from o where soc_code = '00-0000'
)
select
    o.cbsa_code,
    o.soc_code,
    r.occupation_title,
    r.role_family,
    o.oews_year,
    o.employment,
    o.jobs_per_1000,
    o.location_quotient,
    o.a_mean as annual_mean_wage,
    o.a_pct10 as annual_p10_wage,
    o.a_pct25 as annual_p25_wage,
    o.a_median as annual_median_wage,
    o.a_pct75 as annual_p75_wage,
    o.a_pct90 as annual_p90_wage,
    o.is_top_coded,
    a.all_occupations_median,
    o.a_median / nullif(a.all_occupations_median, 0) as pay_vs_all_occupations
from o
join {{ ref('soc_role_family') }} r using (soc_code)
join {{ ref('dim_metro') }} m using (cbsa_code)
left join all_occ a using (cbsa_code)
