from __future__ import annotations

import re
from abc import abstractmethod
from asyncio import sleep
from logging import getLogger
from random import randrange
from typing import Any

from aiohttp import ClientSession
from mautrix.types import MessageEventContent, RoomID
from mautrix.util.logging import TraceLogger

from menuflow.utils.util import Util

from ..config import Config
from ..room import Room
from ..utils.flags import RenderFlags


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


def convert_to_int(item: Any) -> dict | list | int:
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

    content: dict

    def __init__(self, room: Room, default_variables: dict) -> None:
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

        if "body" in content:
            content["body"] = re.sub(r"¬¬¬", r"", content["body"])
        if "formatted_body" in content:
            content["formatted_body"] = re.sub(r"¬¬¬", r"", content["formatted_body"])

        await self.room.matrix_client.send_message(room_id=room_id, content=content)

    def render_data(
        self,
        data: dict | list | str,
        flags: RenderFlags = RenderFlags.CONVERT_TO_TYPE
        | RenderFlags.LITERAL_EVAL
        | RenderFlags.REMOVE_QUOTES,
    ) -> dict | list | str:
        """It renders the data using the default variables and the room variables.

        Parameters
        ----------
        data : Any
            The data to be rendered.
        flags : RenderFlags
            The flags to be used in the rendering.

        Returns
        -------
            The rendered data, which can be a dictionary, list, or string.

        """

        if not (isinstance(data, (str, dict, list)) and data):
            return data

        variables = self.default_variables | self.room.all_variables

        if RenderFlags.CUSTOM_ESCAPE in flags:
            variables, changed = Util.custom_escape(variables, escape=True)
            if changed:
                flags |= RenderFlags.CUSTOM_UNESCAPE

        return Util.recursive_render(data=data, variables=variables, flags=flags)

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
