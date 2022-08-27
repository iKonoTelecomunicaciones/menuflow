from __future__ import annotations

from typing import Any, Dict, List, Optional
import asyncio
import logging

from asyncpg import Record
from attr import dataclass
from jinja2 import Template
from markdown import markdown
import attr

from maubot.client import MaubotMatrixClient
from mautrix.types import Format, MessageType, RoomID, SerializableAttrs, TextMessageEventContent
from mautrix.util.logging import TraceLogger

from .db.models import User, Variable
from .primitive import OConnection


class BaseLogger:
    log: TraceLogger = logging.getLogger("maubot.menu")


@dataclass
class Case(SerializableAttrs):
    id: str = attr.ib(metadata={"json": "id"})
    o_connection: str = attr.ib(default=None, metadata={"json": "o_connection"})


@dataclass
class Message(SerializableAttrs, BaseLogger):
    id: str = attr.ib(metadata={"json": "id"})
    text: str = attr.ib(metadata={"json": "text"})
    wait: int = attr.ib(default=None, metadata={"json": "wait"})
    o_connection: OConnection = attr.ib(default=None, metadata={"json": "o_connection"})
    variable: str = attr.ib(default=None, metadata={"json": "variable"})
    # actions: List[str] = attr.ib(default=None, metadata={"json": "actions"}, factory=list)

    async def run(
        self, user: User, room_id: RoomID, client: MaubotMatrixClient, i_variable: str = None
    ):
        """It sends a message to the user, and updates the menu

        Parameters
        ----------
        user : User
            The user object
        room_id : RoomID
            The room ID of the room the user is in.
        client : MaubotMatrixClient
            The MaubotMatrixClient object.
        i_variable : str
            The variable that the user has inputted.

        """

        self.log.debug(f"Running message {self.id}")

        if self.variable and i_variable:
            user.set_variable(variable=Variable(self.variable, i_variable))

        if user.state == "SHOW_MESSAGE":
            msg_content = TextMessageEventContent(
                msgtype=MessageType.TEXT,
                body=self.text,
                format=Format.HTML,
                formatted_body=markdown(self.text.format(**user.variable_by_id)),
            )
            await client.send_message(room_id=room_id, content=msg_content)
            user.update_menu(context=self.o_connection)


@dataclass
class Pipeline(SerializableAttrs, BaseLogger):
    id: str = attr.ib(metadata={"json": "id"})
    validation: str = attr.ib(metadata={"json": "validation"})
    variable: str = attr.ib(default=None, metadata={"json": "variable"})
    cases: List[Case] = attr.ib(metadata={"json": "cases"}, factory=list)

    @property
    def template(self) -> Template:
        return Template(self.validation)

    def run(self, user: User):
        """It takes a user object, runs the pipeline,
        and updates the user's menu based on the result

        Parameters
        ----------
        user : User
            User

        """

        self.log.debug(f"Running pipeline {self.id}")

        case_res = None

        self.log.debug(f"#### {user.variable_by_id}")

        try:
            res = self.template.render(**user.variable_by_id)
            if res == "True":
                res = True

            if res == "False":
                res = False

            case_res = Case(id=res)
        except Exception as e:
            self.log.warning(f"An exception has occurred in the pipeline {self.id} :: {e}")
            case_res = Case(id="except")

        for case in self.cases:
            if case_res.id == case.id:
                user.update_menu(context=case.o_connection)
                self.log.debug(f"##### {user}")
                break


@dataclass
class Menu(SerializableAttrs, BaseLogger):
    id: str = attr.ib(metadata={"json": "id"})
    global_variables: Optional[List[Variable]] = attr.ib(
        metadata={"json": "global_variables"}, factory=list
    )
    messages: List[Message] = attr.ib(metadata={"json": "messages"}, factory=list)
    pipelines: List[Pipeline] = attr.ib(metadata={"json": "pipelines"}, factory=list)

    message_by_id: Dict = {}
    pipeline_by_id: Dict = {}

    def get_message_by_id(self, message_id: str) -> "Message" | None:
        """ "If the message is in the cache, return it. Otherwise,
        search the list of messages for the message with the given ID,
        and if it's found, add it to the cache and return it."

        The first line of the function is a try/except block.
        If the message is in the cache, the first line will return it.
        If the message is not in the cache, the first line will raise a KeyError exception,
        which will be caught by the except block

        Parameters
        ----------
        message_id : str
            The ID of the message to get.

        Returns
        -------
            A message object

        """

        try:
            return Message.deserialize(self.message_by_id[message_id].serialize())
        except KeyError:
            pass

        for message in self.messages:
            if message_id == message.id:
                self.message_by_id[message_id] = message
                return Message.deserialize(message.serialize())

    def get_pipeline_by_id(self, pipeline_id: str) -> "Pipeline" | None:
        """If the pipeline is in the cache, return it.
        Otherwise, search the list of pipelines for the pipeline with the given ID,
        and if found, add it to the cache and return it

        Parameters
        ----------
        pipeline_id : str
            The ID of the pipeline you want to get.

        Returns
        -------
            A pipeline object

        """

        try:
            return Pipeline.deserialize(self.pipeline_by_id[pipeline_id].serialize())
        except KeyError:
            pass

        for pipeline in self.pipelines:
            if pipeline_id == pipeline.id:
                self.pipeline_by_id[pipeline_id] = pipeline
                return Pipeline.deserialize(pipeline.serialize())
