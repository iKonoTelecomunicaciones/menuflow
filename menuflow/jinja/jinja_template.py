from datetime import datetime
from re import match

from fuzzywuzzy import fuzz
from jinja2 import BaseLoader, Environment
from jinja2_ansible_filters import AnsibleCoreFiltersExtension

from .jinja_filters import combine, dict2items, get_attrs, items2dict, phone_numbers, strftime_tz
from .jinja_tests import is_valid_date
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

jinja_env.filters["dict2items"] = dict2items
"""
Converts a dictionary to a list of dictionaries with key and value
e.g
{{ {"a": 1, "b": 2} | dict2items("key", "value") }}
"""

jinja_env.filters["items2dict"] = items2dict
"""
Converts a list of dictionaries to a dictionary
e.g
{{ [{'key': 'a', 'value': 1}, {'key': 'b', 'value': 2}] | items2dict("key", "value") }}
"""

jinja_env.filters["phonenumbers"] = phone_numbers
"""
Converts a phone number to a string
e.g
{{ ("3178901234" | phonenumbers("CO")).country_code }}
{{ (("0431234567" | phonenumbers("CH")).description_for_number("it")) }}
"""

jinja_env.filters["dir"] = get_attrs
"""
Returns the attributes of an object
e.g
{{ "Hello" | dir }}
"""

jinja_env.filters["combine"] = combine
"""
Combines dictionaries into a single dictionary
e.g
{{ {"a": 1, "b": 2} | combine({"c": 3}, {"d": 4}) }}
"""

jinja_env.tests["valid_date"] = is_valid_date
"""
Checks if a variable is a valid date
e.g
{% if "2025-01-01" is valid_date %}The date is valid{% else %}The date is not valid{% endif %}
{% if "2025:01:01" is valid_date("%Y:%m:%d") %}The date is valid {% else %}The date is not valid{% endif %}
"""
