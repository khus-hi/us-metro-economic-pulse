{#
  Fails for rows where the column is outside [min_value, max_value].
  Nulls pass (use not_null for that). Usage in yml:
    - accepted_range: {arguments: {min_value: 0, max_value: 30}}
#}
{% test accepted_range(model, column_name, min_value=none, max_value=none) %}
select *
from {{ model }}
where {{ column_name }} is not null
  and (
    {% if min_value is not none %} {{ column_name }} < {{ min_value }} {% else %} false {% endif %}
    or
    {% if max_value is not none %} {{ column_name }} > {{ max_value }} {% else %} false {% endif %}
  )
{% endtest %}
