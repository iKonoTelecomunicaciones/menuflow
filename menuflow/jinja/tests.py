from datetime import datetime
from logging import Logger, getLogger

from jinja2 import Environment

log: Logger = getLogger("menuflow.jinja_tests")


def is_valid_date(value: str, format: str | None = None) -> bool:
    """Checks if a variable is a valid date

    Args:
        value (str): The value to check

    Returns:
        bool: True if the value is a valid date, False otherwise

    Jinja usage:
        {% if "2025-01-01" is valid_date %}The date is valid{% endif %}
        {% if "2025:01:01" is valid_date("%Y:%m:%d") %}The date is valid{% endif %}
    """
    format = ["%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%Y/%m/%d"] if not format else [format]
    for fmt in format:
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False


def register_tests(env: Environment):
    """Register custom Jinja2 tests in the given environment.

    Args:
        env (Environment): The Jinja2 environment.
    """
    env.tests.update({"valid_date": is_valid_date})
