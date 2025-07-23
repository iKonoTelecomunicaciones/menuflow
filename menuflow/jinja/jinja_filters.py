from collections.abc import Mapping, Sequence
from datetime import datetime
from logging import Logger, getLogger

import pytz
from glom import glom, merge

from .filters.phone_numbers import PhoneNumbers

log: Logger = getLogger("menuflow.jinja_filters")


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


def dict2items(data_dict: dict, key_name: str = "key", value_name: str = "value"):
    """Converts a dictionary to a list of dictionaries with key and value.

    Args:
        data_dict (dict): The dictionary to convert
        key_name (str): The name of the key in the new dictionaries
        value_name (str): The name of the value in the new dictionaries

    Returns:
        list: A list of dictionaries with the key and value of the original dictionary
    """

    if not isinstance(data_dict, Mapping):
        raise ValueError(f"dict2items requires a dictionary, got {type(data_dict)} instead.")

    return [{key_name: key, value_name: value} for key, value in data_dict.items()]


def items2dict(data_list: list, key_name: str = "key", value_name: str = "value"):
    """Converts a list of dictionaries to a dictionary.

    Args:
        data_list (list): The list of dictionaries to convert
        key_name (str): The name of the key in the new dictionary
        value_name (str): The name of the value in the new dictionary

    Returns:
        dict: A dictionary with the key and value of the original list of dictionaries
    """

    if isinstance(data_list, (str, bytes)) or not isinstance(data_list, Sequence):
        raise ValueError(f"items2dict requires a list, got {type(data_list)} instead.")

    try:
        return {item[key_name]: item[value_name] for item in data_list}
    except KeyError:
        raise ValueError(
            f"items2dict requires each dictionary in the list to contain the keys"
            f"'{key_name}' and '{value_name}', got {data_list} instead."
        )
    except TypeError:
        raise ValueError("items2dict requires a list of dictionaries")


def phone_numbers(phone_number: str, country_code: str | None = None) -> str:
    """Converts a phone number to a string.

    Args:
        phone_number (str): The phone number to convert
        country_code (str): The country code to use

    Returns:
        str: The converted phone number
    """

    return PhoneNumbers(phone_number, country_code)


def get_attrs(obj: object) -> list:
    """Returns the attributes of an object

    Args:
        obj (object): The object to get the attributes of

    Returns:
        list: The attributes of the object
    """
    return dir(obj)


def combine(*args: object) -> object:
    """Combines an object with a list of objects

    Args:
        obj (object): The object to combine
        *args (object): The list of objects to combine
    """
    return glom(args, merge)
