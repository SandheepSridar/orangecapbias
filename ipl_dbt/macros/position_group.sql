{% macro position_group(col) %}
case
    when {{ col }} <= 2 then 'Opener (1-2)'
    when {{ col }} <= 3 then 'Top Order (3)'
    when {{ col }} <= 5 then 'Middle Order (4-5)'
    else 'Finisher (6+)'
end
{% endmacro %}
