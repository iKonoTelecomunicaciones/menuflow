from __future__ import annotations

from abc import abstractmethod
from asyncio import sleep
from json import JSONDecodeError, dumps, loads
from logging import getLogger
from random import randrange
from typing import Any, Dict, List

from aiohttp import ClientSession
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

    def render_data(self, data: Dict | List | str) -> Dict | List | str:
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

        try:
            data = data if isinstance(data, str) else dumps(data)
            data_template = jinja_env.from_string(data)
        except Exception as e:
            self.log.exception(e)
            return

        copy_variables = self.default_variables | self.room.all_variables
        clear_variables = dumps(copy_variables).replace("\\n", "ik-line-break")
        try:
            # if save variables have a string with \n,
            # it will be replaced by ik-line-break to avoid errors when dict is dumped
            # and before return, it will be replaced by \n again to keep the original string
            temp_rendered = data_template.render(**loads(clear_variables))
            temp_rendered = temp_rendered.replace("ik-line-break", "\\n")

            temp_sanitized = convert_to_bool(Util.convert_to_json(temp_rendered))
            if isinstance(temp_sanitized, str):
                temp_sanitized = loads(temp_rendered)

            return temp_sanitized
        except JSONDecodeError:
            temp_rendered = data_template.render(**loads(clear_variables))
            temp_rendered = temp_rendered.replace("ik-line-break", "\\n")
            return convert_to_bool(temp_rendered)
        except KeyError:
            data = loads(data_template.render())
            data = convert_to_bool(data)
            return data
        except Exception as e:
            self.log.exception(e)
            return

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
