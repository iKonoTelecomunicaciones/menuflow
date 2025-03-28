from datetime import datetime
from re import match

from fuzzywuzzy import fuzz
from jinja2 import BaseLoader, Environment
from jinja2_ansible_filters import AnsibleCoreFiltersExtension

from .jinja_filters import strftime_tz
from .matrix_filters import MatrixFilters

jinja_env = Environment(
    autoescape=True,
    loader=BaseLoader,
    extensions=[
        AnsibleCoreFiltersExtension,
        MatrixFilters,
        "jinja2.ext.debug",
        "jinja2.ext.do",
        "jinja2.ext.loopcontrols",
    ],
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
    compare_ratio=lambda text, base_text: fuzz.ratio(text.lower(), base_text.lower())
)
"""
Validates if a text is similar to another text
e.g
{{ compare_ratio("Esteban Galvis", "Esteban Galvis Triana") }}
"""

jinja_env.filters["strftime_tz"] = strftime_tz
"""
Formats the current time according to the timezone
e.g
{{ "%d %m %Y" | strftime_tz("America/Bogota") }}
"""
