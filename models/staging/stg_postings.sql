{{ config(materialized='view', schema='staging') }}
-- Analyst postings (already filtered to analyst titles and deduped by ingest/postings.py).
-- A posting is "open" if it was seen in the most recent postings run.
with src as (select * from {{ source('raw', 'postings') }})
select
    job_key,
    ats,
    board,
    company,
    job_id,
    title,
    nullif(trim(location), '') as location,
    lower(is_remote) in ('true', '1') as is_remote,
    try_cast(nullif(posted_date, '') as date) as posted_date,
    url,
    nullif(tools, '') as tools,
    cast(first_seen as date) as first_seen,
    cast(last_seen as date) as last_seen,
    cast(last_seen as date) = max(cast(last_seen as date)) over () as is_open,
    -- Role family from the title, checked in this order (first match wins).
    case
        when regexp_matches(title, '(?i)product') then 'Product'
        when regexp_matches(title, '(?i)marketing|growth|brand|campaign') then 'Marketing'
        when regexp_matches(title, '(?i)financ|fp&a|investment|credit|risk|pricing|treasury|accounting') then 'Financial'
        when regexp_matches(title, '(?i)operations|supply chain|logistics|workforce|strategy & ops|bizops') then 'Operations'
        when regexp_matches(title, '(?i)\bhealth|clinical|medical|pharma|patient') then 'Healthcare'
        when regexp_matches(title, '(?i)business|strategy|sales|revenue') then 'Business'
        else 'Data'
    end as role_family
from src
