{#
  Grain test: no two rows share the same combination of columns.
  Usage on a model:
    data_tests:
      - unique_combination: {arguments: {columns: [cbsa_code, month_date]}}
#}
{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
