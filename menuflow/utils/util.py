import json
from asyncio import Task, all_tasks
from logging import getLogger
from re import match, sub
from typing import Dict

import jq
from mautrix.types import RoomID, UserID
from mautrix.util.logging import TraceLogger

from ..config import Config

log: TraceLogger = getLogger("menuflow.util")


class Util:
    config: Config
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
            log.debug(f"TASK CANCEL -> {task_name}")

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
            log.warning("Validation parameters can not be None, range validation failed")
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


class UtilLite:
    @staticmethod
    def jq_compile(filter: str, json_data: dict | list) -> dict:
        """
        It compiles a jq filter and json data into a jq command.
        Parameters
        ----------
        filter : str
            The jq filter to be applied.
        json_data : dict | list
            The JSON data to be filtered.
        Returns
        -------
            A dictionary containing the filtered result, error message if any, and status code.
        """

        try:
            compiled = jq.compile(filter)
        except Exception as e:
            return {"result": [], "error": str(e), "status": 400}

        try:
            filtered_result = compiled.input(json_data).all()
        except Exception as e:
            log.exception(f"Error in jq filter: {e} with filter: {filter}")
            return {"result": [], "error": str(e), "status": 421}

        return {"result": filtered_result, "error": None, "status": 200}
