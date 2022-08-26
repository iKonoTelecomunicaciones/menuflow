from __future__ import annotations

from typing import Any, Dict, List, Optional

import attr
from attr import dataclass
from jinja2 import Template
from markdown import markdown
from maubot.client import MaubotMatrixClient
from mautrix.types import (Format, MessageEventContent, MessageType, RoomID,
                           SerializableAttrs)

from .primitive import OConnection
from .user import User


@dataclass
class Variable(SerializableAttrs):
    id: str = attr.ib(metadata={"json": "id"})
    value: Any = attr.ib(metadata={"json": "value"})


@dataclass
class Case(SerializableAttrs):
    id: str = attr.ib(metadata={"json": "id"})
    o_connection: str = attr.ib(default=None, metadata={"json": "o_connection"})


@dataclass
class Message(SerializableAttrs):
    id: str = attr.ib(metadata={"json": "id"})
    text: str = attr.ib(metadata={"json": "text"})
    o_connection: OConnection = attr.ib(default=None, metadata={"json": "o_connection"})
    variable: str = attr.ib(default=None, metadata={"json": "variable"})
    # actions: List[str] = attr.ib(default=None, metadata={"json": "actions"}, factory=list)

    async def run(
        self, user: User, room_id: RoomID, client: MaubotMatrixClient, i_variable: str = None
    ):
        if self.variable and i_variable:
            user.set_variable(variable=Variable(self.variable, i_variable))

        # if self.actions:
        #     for action in self.actions:
        #         getattr(actions, action)(**user.variable_by_id)

        if user.state == "SHOW_MESSAGE":
            msg_content = MessageEventContent(
                msgtype=MessageType.TEXT,
                body=self.text,
                format=Format.HTML,
                formatted_body=markdown(self.text.format(**user.variable_by_id)),
            )
            await client.send_message(room_id=room_id, content=msg_content)
            user.update_menu(context=self.o_connection)


@dataclass
class Pipeline(SerializableAttrs):
    id: str = attr.ib(metadata={"json": "id"})
    validation: str = attr.ib(metadata={"json": "validation"})
    variable: str = attr.ib(default=None, metadata={"json": "variable"})
    cases: List[Case] = attr.ib(metadata={"json": "cases"}, factory=list)

    @property
    def template(self) -> Template:
        return Template(self.validation)

    def run(self, user: User):
        variables = {}
        case_res = None

        if self.variable:
            variable = user.get_varibale(variable_id=self.variable)
            variables = (
                {variable.id: variable.value}
                if user.get_varibale(variable_id=self.variable)
                else None
            )

        try:
            res = self.template.render(**variables)
            case_res = Case(id=res)
        except Exception:
            case_res = Case(id="except")

        for case in self.cases:
            if case_res.id == case.id:
                user.update_menu(context=case.o_connection)
                break


@dataclass
class Menu(SerializableAttrs):
    id: str = attr.ib(metadata={"json": "id"})
    global_variables: Optional[List[Variable]] = attr.ib(
        metadata={"json": "global_variables"}, factory=list
    )
    messages: List[Message] = attr.ib(metadata={"json": "messages"}, factory=list)
    pipelines: List[Pipeline] = attr.ib(metadata={"json": "pipelines"}, factory=list)

    message_by_id: Dict = {}
    pipeline_by_id: Dict = {}

    def get_message_by_id(self, message_id: str) -> "Message" | None:

        try:
            return self.message_by_id[message_id]
        except KeyError:
            pass

        for message in self.messages:
            if message_id == message.id:
                self.message_by_id[message_id] = message
                return message

    def get_pipeline_by_id(self, pipeline_id: str) -> "Pipeline" | None:

        try:
            return self.pipeline_by_id[pipeline_id]
        except KeyError:
            pass

        for pipeline in self.pipelines:
            if pipeline_id == pipeline.id:
                self.pipeline_by_id[pipeline_id] = pipeline
                return pipeline
