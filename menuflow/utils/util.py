import json
from asyncio import Task, all_tasks
from logging import getLogger
from re import match, sub
from typing import Dict

import holidays
from aiohttp import ClientResponse, ClientSession
from mautrix.types import RoomID, UserID
from mautrix.util.logging import TraceLogger

from ..config import Config
from .errors import GettingDataError


class Util:
    config: Config
    log: TraceLogger = getLogger("menuflow.util")
    _main_matrix_regex = "[\\w-]+:[\\w.-]"

    def __init__(self, config: Config):
        self.config = config

    @property
    def months(self) -> Dict[str, int]:
        return {
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "may": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
        }

    @property
    def week_days(self) -> Dict[str, int]:
        return {
            "mon": 1,
            "tue": 2,
            "wed": 3,
            "thu": 4,
            "fri": 5,
            "sat": 6,
            "sun": 7,
        }

    @classmethod
    def is_user_id(cls, user_id: UserID) -> bool:
        """It checks if the user_id is valid matrix user_id

        Parameters
        ----------
        user_id : str
            The user ID to check.

        Returns
        -------
            A boolean value.

        """
        return False if not user_id else bool(match(f"^@{cls._main_matrix_regex}+$", user_id))

    @classmethod
    def is_room_id(cls, room_id: RoomID) -> bool:
        """It checks if the room_id is valid matrix room_id

        Parameters
        ----------
        room_id : str
            The room ID to check.

        Returns
        -------
            A boolean value.

        """
        return False if not room_id else bool(match(f"^!{cls._main_matrix_regex}+$", room_id))

    @classmethod
    def get_tasks_by_name(self, task_name: str) -> Task:
        """It returns a task object from the current event loop, given the task's name
        Parameters
        ----------
        task_name
            The name of the task to find.
        Returns
        -------
            An specific task.
        """

        tasks = all_tasks()
        for task in tasks:
            if task.get_name() == task_name:
                return task

    @classmethod
    async def cancel_task(self, task_name: str):
        """It cancels the inactivity task that is running in the background"""

        task = self.get_tasks_by_name(task_name)
        if task:
            task.cancel()
            self.log.debug(f"TASK CANCEL -> {task_name}")

    @classmethod
    def is_within_range(self, number: int, start: int, end: int) -> bool:
        """ "Return True if number is within the range of start and end, inclusive."

        Parameters
        ----------
        number : int
            the number to check
        start : int
            The start of the range.
        end : int
            The end of the range.

        Returns
        -------
            A boolean value

        """

        if not (number and start and end):
            self.log.warning("Validation parameters can not be None, range validation failed")
            return False

        return start <= number <= end

    @classmethod
    def flow_example(cls, flow_index: int = 0) -> Dict:
        """This function reads a JSON file containing either a cat or dog fact and returns its
        contents as a dictionary.

        Parameters
        ----------
        flow_index : int, optional
            `flow_index` is an integer parameter that specifies the index of the flow to be loaded
            from the `sample_flows` directory. The default value is 0, which means that the first
            flow in the list (`cat_fact.json`) will be loaded if no value is provided for `flow_index

        Returns
        -------
            A dictionary containing the contents of a JSON file specified by the `flow_index` parameter.
            The JSON file is read from the `sample_flows` directory and its contents are loaded
            into a dictionary using the `json.loads()` method.

        """

        flows = ["cat_fact.json", "dog_fact.json"]
        with open(f"menuflow/utils/sample_flows/{flows[flow_index]}", "r") as f:
            return json.loads(f.read())

    def ignore_user(self, mxid: UserID, origin: str) -> bool:
        """It checks if the user ID matches any of the regex patterns in the config file

        Parameters
        ----------
        mxid : UserID
            The user ID of the user who sent the message.
        origin : str
            This is the type of event that triggered the function. It can be one of the following:
            - message
            - invite

        Returns
        -------
            A boolean value.

        """

        user_regex = (
            "menuflow.ignore.messages_from"
            if origin == "message"
            else "menuflow.ignore.invitations_from"
        )

        if self.is_user_id(mxid):
            for pattern in self.config[user_regex]:
                if match(pattern, mxid):
                    return True

        return False

    async def cancel_tasks(self) -> None:
        tasks = all_tasks()
        for task in tasks:
            if match(self.config["menuflow.regex.room_id"], task.get_name()):
                task.cancel()

    # Function to fix malformed lists
    @classmethod
    def fix_malformed_json(cls, value: str) -> str:
        # Replace single quotes with double quotes
        value = value.replace("'", '"')

        # Correct malformed lists inside strings
        # Find a malformed list inside a string and fix the quotes
        value = sub(r'"\[([^]]+)\]"', r"[\1]", value)

        return value

    # Recursive function to convert values to JSON if possible
    @classmethod
    def convert_to_json(cls, value: str | list | dict) -> str | list | dict:
        if isinstance(value, dict):
            # If it's a dictionary, apply the recursive conversion on each key
            return {k: cls.convert_to_json(v) for k, v in value.items()}
        elif isinstance(value, list):
            # If it's a list, apply the recursive conversion on each item
            return [cls.convert_to_json(item) for item in value]
        elif isinstance(value, str):
            # First, fix any malformed format
            value = cls.fix_malformed_json(value)
            try:
                # Try to convert the string to JSON
                converted = json.loads(value)
                # If the result is a dictionary or list, apply recursive conversion
                if isinstance(converted, (dict, list)):
                    return cls.convert_to_json(converted)
                # If not, return the original string (numbers in strings are not modified)
                return value
            except (json.JSONDecodeError, TypeError):
                # If the conversion to JSON fails, return the original value
                return value
        else:
            # If it's not a string, list or dictionary, return the value as is
            return value

    @staticmethod
    def parse_countries_data(languages, subdivisions, countries_data):
        """
        Parse the countries data from the World Bank API and return a list of dictionaries
        with the countries' code, name, languages and subdivisions.

        Parameters
        ----------
        languages : dict[str, list[str]]
            A dictionary with the countries' code as key and a list of languages as value.
        subdivisions : dict[str, list[str]]
            A dictionary with the countries' code as key and a list of subdivisions as value.
        countries_data : list[dict, list[dict]]
            A list with the countries' data from the World Bank API.

        Returns
        -------
            A list of dictionaries with the countries' code, name, languages and subdivisions.
        """

        if not countries_data:
            return []

        countries_with_name = [
            {"id": country["iso2Code"], "name": country["name"]}
            for country in countries_data[1]
            if country["iso2Code"] in languages.keys()
        ]

        countries = [
            {
                "code": country["id"],
                "name": country["name"],
                "languages": languages.get(country["id"]),
                "subdivisions": subdivisions.get(country["id"]),
            }
            for country in countries_with_name
        ]

        return countries

    async def get_countries(self) -> list[dict]:
        """
        Fetch the countries data from the World Bank API and return a list of dictionaries
        with the countries' code, name, languages and subdivisions.

        Returns
        -------
            A list of dictionaries with the countries' code, name, languages and subdivisions.
        """
        languages: dict[str, list[str]] = holidays.list_localized_countries()
        subdivisions: dict[str, list[str]] = holidays.list_supported_countries()
        data: ClientResponse = await ClientSession().get(url=self.config["api.get_countries"])

        if data.status != 200 or not data:
            self.log.error(f"Error fetching countries data: {data.status}")
            raise GettingDataError("Error fetching countries data")

        try:
            countries_data: list[dict, list[dict]] = await data.json()
        except Exception as e:
            self.log.error(f"Error parsing countries data: {e}")
            raise GettingDataError("Error parsing countries data")

        return self.parse_countries_data(
            languages=languages, subdivisions=subdivisions, countries_data=countries_data
        )
