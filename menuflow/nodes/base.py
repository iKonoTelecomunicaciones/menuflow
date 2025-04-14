from __future__ import annotations

import ast
import html
import traceback
from abc import abstractmethod
from asyncio import sleep
from json import JSONDecodeError, dumps, loads
from logging import getLogger
from random import randrange
from typing import Any, Dict, List

from aiohttp import ClientSession
from jinja2 import TemplateSyntaxError, UndefinedError
from mautrix.types import MessageEventContent, RoomID
from mautrix.util.logging import TraceLogger

from ..config import Config
from ..jinja.jinja_template import jinja_env
from ..room import Room
from ..utils import Util


def convert_to_bool(item) -> Dict | List | str:
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


def convert_to_int(item: Any) -> Dict | List | int:
    if isinstance(item, dict):
        for k, v in item.items():
            item[k] = convert_to_int(v)
        return item
    elif isinstance(item, list):
        return [convert_to_int(i) for i in item]
    elif isinstance(item, str) and item.isdigit():
        return int(item)
    else:
        return item


def safe_data_convertion(item: Any, _bool: bool = True, _int: bool = True) -> Any:
    if _bool:
        item = convert_to_bool(item)

    if _int:
        item = convert_to_int(item)

    return item


class Base:
    log: TraceLogger = getLogger("menuflow.node")

    config: Config
    session: ClientSession

    content: Dict

    def __init__(self, room: Room, default_variables: Dict) -> None:
        self.room = room
        self.default_variables = default_variables

    @property
    def id(self) -> str:
        return self.content.get("id", "")

    @property
    def type(self) -> str:
        return self.content.get("type", "")

    @classmethod
    def init_cls(cls, config: Config, session: ClientSession):
        cls.config = config
        cls.session = session

    @abstractmethod
    async def run(self):
        pass

    async def set_typing(self, room_id: RoomID):
        """It sets the typing notification for a random amount of time between 1 and 3 seconds

        Parameters
        ----------
        room_id : RoomID
            The room ID of the room you want to send the typing notification to.

        """
        start = self.config["menuflow.typing_notification.start"] or 1
        end = self.config["menuflow.typing_notification.end"] or 3
        typing_time = randrange(start, end)
        await self.room.matrix_client.set_typing(room_id=room_id, timeout=typing_time)
        await sleep(typing_time)

    async def send_message(self, room_id: RoomID, content: MessageEventContent):
        """It sends a message to the room.

        Parameters
        ----------
        room_id : RoomID
            The room ID of the room you want to send the message to.
        content : MessageEventContent
            The content of the message.

        """

        if self.config["menuflow.typing_notification.enable"]:
            await self.set_typing(room_id=room_id)

        await self.room.matrix_client.send_message(room_id=room_id, content=content)

    def render_data(self, data: dict | list | str) -> Dict | List | str:
        """It takes a dictionary or list, converts it to a string,
        and then uses Jinja to render the string

        Parameters
        ----------
        data : Dict | List
            The data to be rendered.

        Returns
        -------
            A dictionary or list.

        """
        self.log.critical(f"Rendering data: {data}")
        dict_variables = self.default_variables | self.room.all_variables

        if isinstance(data, dict):
            for key, value in data.items():
                data[key] = self.render_data(value)
            return data
        elif isinstance(data, list):
            return [self.render_data(item) for item in data]
        elif isinstance(data, str):
            try:
                template = jinja_env.from_string(data)
                temp_rendered = template.render(dict_variables)
            except TemplateSyntaxError as e:
                self.log.exception(e)
                self.log.error(
                    f"func_name: {e.name}, \nline: {e.lineno}, \nerror: {e.message}",
                )
                return None
            except UndefinedError as e:
                self.log.exception(e)
                tb_list = traceback.extract_tb(e.__traceback__)
                traceback_info = tb_list[-1]

                func_name = traceback_info.name
                line: int | None = traceback_info.lineno
                self.log.error(
                    f"func_name: {func_name}, \nline: {line}, \nerror: {e}",
                )
                return None
            except Exception as e:
                self.log.exception(e)
                self.log.error(
                    f"Error rendering data: {e}",
                )
                return None
            try:
                evaluated_body = html.unescape(temp_rendered.replace("'", '"'))
                evaluated_body = ast.literal_eval(evaluated_body)
            except Exception as e:
                return temp_rendered
            else:
                if isinstance(evaluated_body, (dict, list)):
                    return self.render_data(evaluated_body)
                else:
                    return temp_rendered
        else:
            return data

    async def get_o_connection(self) -> str:
        """It returns the ID of the next node to be executed.

        Returns
        -------
            The ID of the next node to be executed.

        """
        # Get the next node from the content of node
        o_connection = self.render_data(self.content.get("o_connection", ""))

        # If the o_connection is None or empty, get the o_connection from the stack
        if o_connection is None or o_connection in ["finish", ""]:
            # If the stack is not empty, get the last node from the stack
            if not self.room.route._stack.empty() and self.type != "subroutine":
                self.log.debug(
                    f"Getting o_connection from route stack: {self.room.route._stack.queue}"
                )
                o_connection = self.room.route._stack.get(timeout=3)

        if o_connection:
            self.log.info(f"Go to o_connection node in [{self.id}]: '{o_connection}'")

        return o_connection
