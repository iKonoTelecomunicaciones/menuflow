import ast
import asyncio
import html
import json
import traceback
from asyncio import Task, all_tasks
from copy import deepcopy
from datetime import datetime, timezone
from logging import getLogger
from re import match, sub

import holidays
import jq
from babel import Locale
from jinja2 import TemplateSyntaxError, UndefinedError
from mautrix.types import LocationInfo, LocationMessageEventContent, RoomID, UserID
from mautrix.util.logging import TraceLogger
from pycountry import countries, subdivisions

from ..config import Config
from ..jinja.env import jinja_env
from ..utils.types import Scopes

log: TraceLogger = getLogger("menuflow.util")


# TODO: remove this function when all flows are migrated to the new render data
def convert_to_bool(item) -> dict | list | str:
    if isinstance(item, dict):
        for k, v in item.items():
            item[k] = convert_to_bool(v)
        return item
    elif isinstance(item, list):
        return [convert_to_bool(i) for i in item]
    elif isinstance(item, str):
        if item.lower() == "true":
            return True
        elif item.lower() == "false":
            return False
        else:
            return item
    else:
        return item


class Util:
    config: Config
    _main_matrix_regex = "[\\w-]+:[\\w.-]"
    _jinja_open_delims = ["{{", "{%", "{#"]
    _jinja_close_delims = ["}}", "%}", "#}"]

    def __init__(self, config: Config):
        self.config = config

    @property
    def months(self) -> dict[str, int]:
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
    def week_days(self) -> dict[str, int]:
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
        return [task for task in tasks if task.get_name() == task_name]

    @classmethod
    async def cancel_task(self, task_name: str):
        """It cancels the inactivity task that is running in the background"""

        if tasks := self.get_tasks_by_name(task_name):
            for task in tasks:
                task.cancel()

            log.debug(f"{len(tasks)} tasks canceled for name -> {task_name}")

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
    def flow_example(cls, flow_index: int = 0) -> dict:
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

    @classmethod
    def jinja_render(
        cls,
        data: str | dict,
        variables: dict = {},
        return_errors: bool = False,
    ) -> dict | list | str:
        """Takes a string, renders it with Jinja, and returns the result.
        Handles HTML entities and Python literal representations,
        safely converting them to their actual characters.

        Parameters
        ----------
        data : str | dict
            The data to be evaluated.
        variables : dict
            The variables to be used in the evaluation.
        return_errors : bool
            If True, it will return the errors instead of ignoring them.

        Returns
        -------
            A dictionary, list or string.

        """
        temp_rendered = data
        has_jinja_delims = any(
            open in data and close in data
            for open, close in zip(cls._jinja_open_delims, cls._jinja_close_delims)
        )

        if has_jinja_delims:
            try:
                template = jinja_env.from_string(data)
                temp_rendered = template.render(variables)
            except TemplateSyntaxError as e:
                txt_error = f"func_name: {e.name}, \nline: {e.lineno}, \nerror: {e.message}"
                log.warning(txt_error)

                if return_errors:
                    log.exception(e)
                    raise Exception(txt_error)
                return None
            except UndefinedError as e:
                tb_list = traceback.extract_tb(e.__traceback__)
                traceback_info = tb_list[-1]
                func_name = traceback_info.name
                line: int | None = traceback_info.lineno

                txt_error = f"func_name: {func_name}, \nline: {line}, \nerror: {e}"
                log.warning(txt_error)

                if return_errors:
                    log.exception(e)
                    raise Exception(txt_error)
                return None
            except Exception as e:
                log.warning(
                    f"Error rendering data: {e}",
                )
                if return_errors:
                    log.exception(e)
                    raise e
                return None

        try:
            evaluated_body = temp_rendered
            evaluated_body = html.unescape(evaluated_body.replace("'", '"'))
            literal_eval_body = ast.literal_eval(evaluated_body)
        except Exception as e:
            pass
        else:
            if isinstance(literal_eval_body, (dict, list)):
                return literal_eval_body
        return evaluated_body

    @classmethod
    def render_data(
        cls,
        data: dict | list | str,
        default_variables: dict = {},
        all_variables: dict = {},
        return_errors: bool = False,
    ) -> dict | list | str:
        """It takes a dictionary or list, converts it to a string,
        and then uses Jinja to render the string

        Parameters
        ----------
        data : dict | list
            The data to be rendered.
        default_variables : dict
            The default variables to be used in the rendering.
        all_variables : dict
            The variables to be used in the rendering.
        return_errors : bool
            If True, it will return the errors instead of ignoring them.

        Returns
        -------
            A dictionary, list or string.

        """
        if not (isinstance(data, (str, dict, list)) and data):
            return data

        if isinstance(data, (dict, list)):
            _data = deepcopy(data)
        else:
            _data = data

        if isinstance(_data, dict):
            for key, value in _data.items():
                _data[key] = cls.render_data(value, default_variables, all_variables)
            return _data

        elif isinstance(_data, list):
            return [cls.render_data(item, default_variables, all_variables) for item in _data]

        elif isinstance(_data, str):
            dict_variables = default_variables | all_variables
            rendered = cls.jinja_render(_data, dict_variables, return_errors)

            if isinstance(rendered, (dict, list)):
                return rendered
            else:
                return cls.convert_to_type(rendered)

        return _data

    # TODO: remove this function when all flows are migrated to the new render data
    @classmethod
    def old_render_data(
        cls, data: dict | list | str, default_variables: dict = {}, all_variables: dict = {}
    ) -> dict | list | str:
        """It takes a dictionary or list, converts it to a string,
        and then uses Jinja to render the string

        Parameters
        ----------
        data : dict | List
            The data to be rendered.
        default_variables : dict
            The default variables to be used in the rendering.
        all_variables : dict
            The variables to be used in the rendering.

        Returns
        -------
            A dictionary or list.

        """

        try:
            data = data if isinstance(data, str) else json.dumps(data)
            data_template = jinja_env.from_string(data)
        except Exception as e:
            log.exception(e)
            return

        copy_variables = default_variables | all_variables
        clear_variables = json.dumps(copy_variables).replace("\\n", "ik-line-break")
        try:
            # if save variables have a string with \n,
            # it will be replaced by ik-line-break to avoid errors when dict is dumped
            # and before return, it will be replaced by \n again to keep the original string
            temp_rendered = data_template.render(**json.loads(clear_variables))
            temp_rendered = temp_rendered.replace("ik-line-break", "\\n")

            temp_sanitized = convert_to_bool(Util.convert_to_json(temp_rendered))
            if isinstance(temp_sanitized, str):
                temp_sanitized = json.loads(temp_rendered)

            return temp_sanitized
        except json.JSONDecodeError:
            temp_rendered = data_template.render(**json.loads(clear_variables))
            temp_rendered = temp_rendered.replace("ik-line-break", "\\n")
            return convert_to_bool(temp_rendered)
        except KeyError:
            data = json.loads(data_template.render())
            data = convert_to_bool(data)
            return data
        except Exception as e:
            log.exception(e)
            return

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

    async def cancel_tasks(self, **kwargs) -> None:
        """Cancel tasks by metadata.

        Parameters
        ----------
        kwargs : dict
            The metadata to cancel the tasks.
        """

        regex_room_id = self.config["menuflow.regex.room_id"]
        for task in all_tasks():
            metadata = getattr(task, "metadata", {})
            if match(regex_room_id, task.get_name()) and all(
                metadata.get(k) == v for k, v in kwargs.items()
            ):
                log.info(f"Cancelling task: {task.get_name()} with metadata: {kwargs}")
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

    @classmethod
    def is_holiday(cls, date: datetime, country_code: str, subdivision_code: str) -> bool:
        """
        Verify if the date is a holiday in the country and subdivision.

        Parameters
        ----------
        date : datetime
            The date to verify.
        country_code : str
            The country code to verify.
        subdivision_code : str
            The subdivision code to verify (the code of a zone of the country,
            like the state or department).

        Returns
        -------
            A boolean value.
        """
        try:
            return date in holidays.country_holidays(country_code, prov=subdivision_code)
        except NotImplementedError as e:
            log.error(
                f"Error getting holidays for country code '{country_code}' - with subdivision code '{subdivision_code}': {e}"
            )
            return False

    @staticmethod
    def parse_countries_data(subdivisions_data, countries_data, translate_to):
        """
        Parse the countries data from the World Bank API and return a list of dictionaries
        with the countries' code, name, languages and subdivisions.

        Parameters
        ----------
        languages : dict[str, list[str]]
            A dictionary with the countries' code as key and a list of languages as value.
        subdivisions_data : dict[str, list[str]]
            A dictionary with the countries' code as key and a list of subdivisions as value.
        countries_data : list[dict, list[dict]]
            A list with the countries' data from the World Bank API.
        translate_to : str
            The language to use for the countries' names.

        Returns
        -------
            A list of dictionaries with the countries' code, name, languages and subdivisions.
        """

        if not countries_data or not subdivisions:
            return []

        locale = Locale(translate_to)
        countries_code = [country.alpha_2 for country in countries_data if country.alpha_2]
        countries_name = [
            {
                country.alpha_2: locale.territories.get(country.alpha_2)
                for country in countries_data
            }
        ]
        subdivisions_dict = [
            {
                country_code: [
                    {
                        # pycountry code is in the format "country_code-subdivision_code"
                        # but the holidays library uses the format "subdivision_code"
                        # so we need to split the code and get the last part
                        # to get the subdivision code
                        subdivision.code.split("-")[-1]: locale.territories.get(subdivision.code)
                        or subdivision.name
                    }
                    for subdivision in subdivisions
                ]
                for country_code, subdivisions in subdivisions_data.items()
            }
        ]

        data_countries = {
            "countries": countries_code,
            "labels": countries_name,
            "subdivisions": subdivisions_dict,
        }
        return data_countries

    async def get_countries(self, language: str) -> list[dict]:
        """
        Fetch the countries data from the World Bank API and return a list of dictionaries
        with the countries' code, name, languages and subdivisions.
        Parameters
        ----------
        language : str
            The language to use for the countries' names.

        Returns
        -------
            A list of dictionaries with the countries' code, name, languages and subdivisions.
        """
        holidays_subdivisions: dict[str, list[str]] = holidays.list_supported_countries()

        # Get the list of countries from the holidays library, in holidays library, the alpha-2
        # code  of United Kingdom  is "UK" but this code is not used in pycountry instead
        # it uses "GB", so we need to convert it to "GB" in pycountry to get the country name
        # and the subdivisions
        countries_data: list[dict] = [
            (countries.get(alpha_2=code) if code != "UK" else countries.get(alpha_2="GB"))
            for code in holidays_subdivisions.keys()
        ]

        subdivisions_data: dict[str, list[str]] = {}

        for country_code, country_subdivisions in holidays_subdivisions.items():
            if country_subdivisions:
                # Convert the country code to the pycountry format
                # in holidays library, the alpha-2 code of United Kingdom is "UK"
                # but this code is not used in pycountry instead it uses "GB"
                # so we need to convert it to "GB" in pycountry to get the country name
                # and the subdivisions
                if country_code == "UK":
                    country_code = "GB"

                country_subdivisions_data = [
                    subdivisions.get(code=f"{country_code}-{subdivision_code}")
                    for subdivision_code in country_subdivisions
                    if subdivisions.get(code=f"{country_code}-{subdivision_code}")
                ]

                subdivisions_data[country_code] = country_subdivisions_data

        return self.parse_countries_data(
            subdivisions_data=subdivisions_data,
            countries_data=countries_data,
            translate_to=language,
        )

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
            status = 400
            compiled = jq.compile(filter)
            status = 421
            filtered_result = compiled.input(json_data).all()
        except Exception as error:
            return {"result": [], "error": str(error), "status": status}

        return {"result": filtered_result, "error": None, "status": 200}

    @staticmethod
    def convert_to_type(value: str) -> str | int | float | bool | None:
        """
        Convert a string representation into its corresponding Python type.
        This method attempts to interpret a string and return its most likely
        Python type.

        Parameters
        ----------
        value : str
            The value to be converted.

        Returns
        -------
            The value converted to the appropriate type.

        Examples
        --------
            Basic numeric conversion:
            >>> convert_to_type("123")
            123
            >>> convert_to_type("45.67")
            45.67
            Boolean and None conversion:
            >>> convert_to_type("true")
            True
            >>> convert_to_type("False")
            False
            >>> convert_to_type("None")
            None
            Quoted strings:
            >>> convert_to_type("'Hello'")
            'Hello'
            >>> convert_to_type('"World"')
            'World'
            Non-convertible strings remain unchanged:
            >>> convert_to_type("Hello123")
            'Hello123'
            >>> convert_to_type("12a")
            '12a'
        """
        # If the value is a string in double quotes like "'Hello'" or '"World"',
        # remove the outer quotes and return the value as a string.
        enclosers = value[0] + value[-1] if value else ""
        if enclosers == '""' or enclosers == "''":
            return value[1:-1]

        permitted_types = {
            True: ("true", "True"),
            False: ("false", "False"),
            None: ("none", "None"),
        }

        for type in (int, float):
            try:
                new_value = type(value)
            except Exception:
                continue
            else:
                return new_value if str(new_value) == value else value

        for type, values in permitted_types.items():
            if value in values:
                return type

        return value

    @staticmethod
    def get_scope_and_key(
        variable_id: str,
        default_scope: Scopes = Scopes.ROUTE,
    ) -> tuple[Scopes, str]:
        """Get the scope and key from a variable id

        Parameters
        ----------
        variable_id : str
            The variable id to get the scope and key from.
        default_scope : Scopes
            The default scope to use if the variable id does not have a scope.

        Returns
        -------
            A tuple containing the scope and key.
        """
        if isinstance(variable_id, int):
            variable_id = str(variable_id)

        parts = variable_id.split(".", maxsplit=1)

        if len(parts) == 2 and parts[0] in Scopes._value2member_map_:
            scope: Scopes = Scopes._value2member_map_.get(parts[0], Scopes.UNKNOWN)
            key = parts[1]
        else:
            scope: Scopes = default_scope
            key = variable_id

        return scope, key

    @staticmethod
    def extract_location_info(content: LocationMessageEventContent) -> dict:
        """Extracts the location information from the content.

        Parameters
        ----------
        content : LocationMessageEventContent
            The content of the location message event.

        Returns
        -------
        dict
            The location information.
        """

        status = {"status": "success"}

        latitude = longitude = None
        try:
            # The geo_uri is in the format "geo:latitude,longitude"
            _, coords = content.geo_uri.split(":", 1)
            latitude, longitude = coords.split(",", 1)
        except ValueError:
            log.error(
                f"The geo_uri has changed, return the original geo_uri in response: {content.geo_uri}"
            )
            status.update({"status": "geo_uri_changed", "geo_uri": content.geo_uri})

        data = content.body
        if content.body.startswith("Location: "):
            parts = content.body.removeprefix("Location: ").split("\n")
            if len(parts) == 3:
                data = {"name": parts[0], "address": parts[1], "url": parts[2]}
            else:
                log.warning(
                    f"The body of the location message event content has changed, return the original body: {content.body}"
                )
                status["status"] = (
                    "body_changed"
                    if status["status"] == "success"
                    else "body_changed_and_geo_uri_changed"
                )

        thumbnail = content.info
        if isinstance(content.info, LocationInfo):
            info = content.info.serialize()
            thumbnail = {
                k: info.get(k) for k in ("thumbnail_url", "thumbnail_info", "thumbnail_file")
            }

        return {
            "location": {"latitude": latitude, "longitude": longitude, "data": data},
            "thumbnail": thumbnail,
            **status,
        }

    @staticmethod
    def create_task_by_metadata(coro, *, name: str = None, metadata: dict = None) -> Task:
        """Create a task by name and metadata.

        Parameters
        ----------
        coro: coroutine
            The coroutine to create the task from.
        name: str
            The name of the task.
        metadata: dict
            The metadata of the task.

        Returns
        -------
            The created task.
        """

        log.warning(f"CREATING TASK: {name} with metadata: {metadata}")
        task = asyncio.create_task(coro, name=name)
        task.metadata = metadata or {}
        task.created_at = datetime.now(timezone.utc).timestamp()
        return task
