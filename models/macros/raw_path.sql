{# Where the ingest step lands files. Override with PULSE_DATA_DIR. #}
{% macro raw_path(rel) -%}
'{{ env_var("PULSE_DATA_DIR", "../data") }}/{{ rel }}'
{%- endmacro %}

{# Run date (YYYY-MM-DD folder) from a landed file's path. #}
{% macro run_date_from(filename_col) -%}
cast(regexp_extract({{ filename_col }}, '/(\d{4}-\d{2}-\d{2})/', 1) as date)
{%- endmacro %}
