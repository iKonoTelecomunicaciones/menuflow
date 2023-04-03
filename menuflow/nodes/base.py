from __future__ import annotations

from abc import abstractmethod
from asyncio import create_task, sleep
from json import JSONDecodeError, dumps, loads
from logging import getLogger
from random import randrange
from typing import Any, Dict, List

from aiohttp import ClientSession
from mautrix.client import Client as MatrixClient
from mautrix.types import MessageEventContent, RoomID
from mautrix.util.logging import TraceLogger

from ..config import Config
from ..jinja.jinja_template import jinja_env
from ..room import Room


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
    matrix_client: MatrixClient
    session: ClientSession

    data: Dict
    room: Room

    @property
    def id(self) -> str:
        return self.data.get("id", "")

    @property
    def type(self) -> str:
        return self.data.get("type", "")

    @classmethod
    def init_cls(cls, config: Config, session: ClientSession, default_variables: Dict):
        cls.config = config
        cls.session = session
        cls.variables = default_variables or {}

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

        # async def send():
        #     if self.config["menuflow.typing_notification.enable"]:
        #         await self.set_typing(room_id=room_id)

        #     await self.room.matrix_client.send_message(room_id=room_id, content=content)

        if self.config["menuflow.typing_notification.enable"]:
            await self.set_typing(room_id=room_id)

        await self.room.matrix_client.send_message(room_id=room_id, content=content)

        # create_task(send())

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

        if isinstance(data, str):
            data_template = jinja_env.from_string(data)
        else:
            try:
                data_template = jinja_env.from_string(dumps(data))
            except Exception as e:
                self.log.exception(e)
                return

        self.variables.update(self.room._variables)

        try:
            data = loads(data_template.render(**self.variables))
            data = convert_to_bool(data)
            return data
        except JSONDecodeError:
            data = data_template.render(**self.variables)
            return convert_to_bool(data)
        except KeyError:
            data = loads(data_template.render())
            data = convert_to_bool(data)
            return data
