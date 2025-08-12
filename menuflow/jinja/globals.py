import uuid
from datetime import datetime
from re import match

from fuzzywuzzy import fuzz
from jinja2 import Environment


def env_summary(env: Environment) -> dict:
    """Returns a dictionary with the filters, tests and globals of the environment

    Returns:
        dict: A dictionary with the filters, tests and globals of the environment
    """

    return {
        "filters": list(env.filters.keys()),
        "tests": list(env.tests.keys()),
        "globals": list(env.globals.keys()),
    }


def register_globals(env: Environment):
    """Register the globals in the environment"""

    env.globals.update(utcnow_isoformat=lambda: datetime.utcnow().isoformat())
    """
    Return the time formatted according to ISO.
    e.g
    {{ utcnow_isoformat() }}
    """

    env.globals.update(utcnow=lambda: datetime.utcnow())
    """
    Construct a UTC datetime from time.time().
    e.g
    {{ utcnow() }}
    """

    env.globals.update(datetime_format=lambda date, format: datetime.strptime(date, format))
    """
    Converts a string to a datetime with a specific format
    e.g
    {{ datetime_format("14 09 1999", "%d %m %Y") }}
    """

    env.globals.update(match=lambda pattern, value: bool(match(pattern, value)))
    """
    Validates if a pattern matches a variable
    e.g
    {{ match("^(0[1-9]|[12][0-9]|3[01])\s(0[1-9]|1[012])\s(19[0-9][0-9]|20[0-9][0-9])$", "14 09 1999") }}
    """

    env.globals.update(
        compare_ratio=lambda text, base_text: fuzz.ratio(text.lower(), base_text.lower())
    )
    """
    Validates if a text is similar to another text
    e.g
    {{ compare_ratio("Lorem ipsum dolor sit", "Lorem ipsum dolor sit amet") }}
    """

    env.globals.update(uuid=lambda: str(uuid.uuid4()))
    """
    Generates a random UUID
    e.g
    {{ uuid() }}
    """

    env.globals.update(env=lambda: env_summary(env))
    """
    Returns a dictionary with the filters, tests and globals of the environment
    e.g
    {{ env() }}
    """
