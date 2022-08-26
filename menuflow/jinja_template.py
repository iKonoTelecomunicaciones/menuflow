import re

from jinja2 import Template
from jinja2.filters import FILTERS, environmentfilter


@environmentfilter
def validate_regex(environment, value: str, arg: str) -> bool:
    if re.compile(value, arg):
        return True
    else:
        return False

FILTERS["validate_regex"] = validate_regex
