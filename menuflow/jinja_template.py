import re

from jinja2.filters import FILTERS


def validate_regex(value: str, arg: str) -> bool:
    if re.compile(value, arg):
        return True
    else:
        return False

FILTERS["validate_regex"] = validate_regex
