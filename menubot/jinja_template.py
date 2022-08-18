from jinja2 import Template

# Basic rules

NUMBER = Template(
    "{% if i_variable.isdigit() %}True{% endif %}"
)


# Checks for validations

IS_EQUAL = Template(
    "{% if var_x == var_y %}{{ True }}{% else %}{{ False }}{% endif %}"
)

NOT_IS_EQUAL = Template(
    "{% if var_x != var_y %}{{ True }}{% else %}{{ False }}{% endif %}"
)

GREATER_THAN = Template(
    "{% if var_x > var_y %}{{ True }}{% else %}{{ False }}{% endif %}"
)

LESS_THAN = Template(
    "{% if var_x < var_y %}{{ True }}{% else %}{{ False }}{% endif %}"
)

START_WITH = Template(
    "{% if var_x.startswith(var_y) %}{{ True }}{% else %}{{ False }}{% endif %}"
)

END_WITH = Template(
    "{% if var_x.endswith(var_y) %}{{ True }}{% else %}{{ False }}{% endif %}"
)

DEFAULT = Template("{{ False }}")
