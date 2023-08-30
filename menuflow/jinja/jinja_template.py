from datetime import datetime
from re import match

from fuzzywuzzy import fuzz
from jinja2 import BaseLoader, Environment
from jinja2_ansible_filters import AnsibleCoreFiltersExtension
from jinja2_matrix_filters import MatrixFiltersExtension

jinja_env = Environment(
    autoescape=True,
    loader=BaseLoader,
    extensions=[AnsibleCoreFiltersExtension, MatrixFiltersExtension],
)

jinja_env.globals.update(utcnow_isoformat=lambda: datetime.utcnow().isoformat())
"""
Return the time formatted according to ISO.
e.g
{{ utcnow_isoformat() }}
"""

jinja_env.globals.update(utcnow=lambda: datetime.utcnow())
"""
Construct a UTC datetime from time.time().
e.g
{{ utcnow() }}
"""

jinja_env.globals.update(datetime_format=lambda date, format: datetime.strptime(date, format))
"""
Converts a string to a datetime with a specific format
e.g
{{ datetime_format("14 09 1999", "%d %m %Y") }}
"""


jinja_env.globals.update(match=lambda pattern, value: bool(match(pattern, value)))
"""
Validates if a pattern matches a variable
e.g
{{ match("^(0[1-9]|[12][0-9]|3[01])\s(0[1-9]|1[012])\s(19[0-9][0-9]|20[0-9][0-9])$", "14 09 1999") }}
"""

jinja_env.globals.update(
    compare_ratio=lambda result_text, text, ratio: fuzz.ratio(result_text.lower(), text.lower())
    >= ratio
)
"""
Validates if a text is similar to another text
e.g
{{ compare_ratio("Esteban Galvis", "Esteban Galvis Triana", 80) }}
"""
