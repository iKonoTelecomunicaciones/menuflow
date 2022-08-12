from jinja2 import Template

# Basic rules

NUMBER = Template(
    "{% if i_variable.isdigit() %}{{ True }}{% else %} {{ i_rule_fail_message }} {% endif %}"
)


# Checks for validations

IS_EQUAL = Template(
    "{% if var_x == var_y %}{{ o_connection }}{% else %}{{ else_o_connection }}{% endif %}"
)

NOT_IS_EQUAL = Template(
    "{% if var_x != var_y %}{{ o_connection }}{% else %}{{ else_o_connection }}{% endif %}"
)

GREATER_THAN = Template(
    "{% if var_x > var_y %}{{ o_connection }}{% else %}{{ else_o_connection }}{% endif %}"
)

LESS_THAN = Template(
    "{% if var_x < var_y %}{{ o_connection }}{% else %}{{ else_o_connection }}{% endif %}"
)

DEFAULT = Template("{{ else_o_connection }}")
