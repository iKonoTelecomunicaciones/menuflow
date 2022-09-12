from __future__ import annotations

from typing import Dict, List

from aiohttp import ClientSession
from attr import dataclass, ib
from jinja2 import Template
from markdown import markdown

from maubot.client import MaubotMatrixClient
from mautrix.types import Format, MessageType, RoomID, SerializableAttrs, TextMessageEventContent

from .utils.base_logger import BaseLogger
from .utils.primitive import OConnection


@dataclass
class Case(SerializableAttrs):
    id: str = ib(metadata={"json": "id"})
    o_connection: str = ib(default=None, metadata={"json": "o_connection"})


@dataclass
class Node(SerializableAttrs, BaseLogger):
    id: str = ib(metadata={"json": "id"})
    type: str = ib(metadata={"json": "type"})


@dataclass
class Message(Node):

    text: str = ib(metadata={"json": "text"})
    o_connection: OConnection = ib(default=None, metadata={"json": "o_connection"})
    variable: str = ib(default=None, metadata={"json": "variable"})

    @property
    def template(self) -> Template:
        return Template(self.text)

    async def show_message(self, variables: dict, room_id: RoomID, client: MaubotMatrixClient):
        """It takes a dictionary of variables, a room ID, and a client,
        and sends a message to the room with the template rendered with the variables

        Parameters
        ----------
        variables : dict
            A dictionary of variables to pass to the template.
        room_id : RoomID
            The room ID to send the message to.
        client : MaubotMatrixClient
            The MaubotMatrixClient instance that is running the plugin.

        """

        msg_content = TextMessageEventContent(
            msgtype=MessageType.TEXT,
            body=self.text,
            format=Format.HTML,
            formatted_body=markdown(self.template.render(**variables)),
        )
        await client.send_message(room_id=room_id, content=msg_content)


@dataclass
class Input(Message):
    validation: str = ib(default=None, metadata={"json": "validation"})
    cases: List[Case] = ib(metadata={"json": "cases"}, factory=list)

    @property
    def rule(self) -> Template:
        return Template(self.validation)

    async def run(self, variables: dict) -> OConnection:
        """It takes a dictionary of variables, runs the rule,
        and returns the connection that matches the case

        Parameters
        ----------
        variables : dict
            dict

        Returns
        -------
            The OConnection object

        """

        self.log.debug(f"Running pipeline {self.id}")

        case_res = None

        try:
            res = self.rule.render(**variables)
            if res == "True":
                res = True

            if res == "False":
                res = False

            case_res = Case(id=res)

        except Exception as e:
            self.log.warning(f"An exception has occurred in the pipeline {self.id} :: {e}")
            case_res = Case(id="except")

        self.log.debug(case_res)

        for case in self.cases:
            if case_res.id == case.id:
                return case.o_connection


@dataclass
class Response:
    cases: List[Case] = ib(metadata={"json": "cases"}, factory=list)


@dataclass
class HTTPRequest(Node):
    method: str = ib(metadata={"json": "method"})
    url: str = ib(metadata={"json": "url"})
    response: Response = ib(metadata={"json": "response"})
    variables: Dict = ib(metadata={"json": "variables"}, factory=dict)
    query_params: Dict = ib(metadata={"json": "variables"}, factory=dict)
    headers: Dict = ib(metadata={"json": "variables"}, factory=dict)
    data: Dict = ib(metadata={"json": "variables"}, factory=dict)

    async def request(self, session: ClientSession) -> None:

        response = await session.request(
            self.method, self.url, headers=self.headers, params=self.query_params, json=self.data
        )

        # response_data = await response.json()

        # for variable in self.variables:
