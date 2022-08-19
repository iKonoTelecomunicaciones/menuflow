import re

from jinja2 import Template
from jinja2.filters import FILTERS, environmentfilter


@environmentfilter
def switch(environment, cases: Dict, attribute: Any) -> Any:
    if attribute in cases:
        return cases[opt]
    else:
        return cases["default"]

@environmentfilter
def validate_regex(environment, value: str, arg: str) -> bool:
    if re.compile(value, arg):
        return True
    else:
        return False


FILTERS["switch"] = switch
FILTERS["validate_regex"] = validate_regex
