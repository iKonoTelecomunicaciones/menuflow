from datetime import datetime
from logging import Logger, getLogger

import pytz

log: Logger = getLogger("menuflow.room")


def strftime_tz(str_format: str, tz: str = None) -> str:
    """This function is used to format the current time according to the timezone.
    Args:
        str_format (str): The format to use
        tz (str, optional): The timezone to use. Defaults to None.
    Returns:
        str: The formatted time
    """
    format = pytz.timezone(tz) if tz else pytz.utc
    return datetime.now(format).strftime(str_format)
