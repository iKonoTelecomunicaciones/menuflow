from datetime import datetime
from logging import Logger, getLogger

log: Logger = getLogger("menuflow.jinja_tests")


def is_valid_date(value: str, format: str | None = None) -> bool:
    """Checks if a variable is a valid date

    Args:
        value (str): The value to check

    Returns:
        bool: True if the value is a valid date, False otherwise
    """
    format = ["%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%Y/%m/%d"] if not format else [format]
    for fmt in format:
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False
