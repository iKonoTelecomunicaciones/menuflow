from __future__ import annotations

from typing import Dict, Tuple

from aiohttp import BasicAuth, ClientSession
from aiohttp.client_exceptions import ContentTypeError
from attr import dataclass, ib
from mautrix.util.config import RecursiveDict
from ruamel.yaml.comments import CommentedMap

from ..user import User
from .switch import Switch


@dataclass
class HTTPRequest(Switch):
    method: str = ib(default=None, metadata={"json": "method"})
    url: str = ib(default=None, metadata={"json": "url"})
    __variables: Dict = ib(metadata={"json": "variables"}, factory=dict)
    cookies: Dict = ib(metadata={"json": "cookies"}, factory=dict)
    query_params: Dict = ib(metadata={"json": "query_params"}, factory=dict)
    headers: Dict = ib(metadata={"json": "headers"}, factory=dict)
    basic_auth: Dict = ib(metadata={"json": "basic_auth"}, factory=dict)
    data: Dict = ib(metadata={"json": "data"}, factory=dict)

    async def request(self, user: User, session: ClientSession) -> Tuple(int, str):

        request_body = {}

        if self.query_params:
            request_body["params"] = self.query_params

        if self.basic_auth:

            request_body["auth"] = BasicAuth(
                self.basic_auth["login"],
                self.basic_auth["password"],
            )
        if self.headers:
            request_body["auth"] = self.headers

        if self.data:
            request_body["json"] = self.data

        response = await session.request(self.method, self.url, **request_body)

        variables = {}
        o_connection = None

        if self.cookies:
            for cookie in self.cookies:
                variables[cookie] = response.cookies.output(cookie)

        self.log.debug(
            f"node: {self.id} method: {self.method} url: {self.url} status: {response.status}"
        )

        # Tulir and its magic since time immemorial
        try:
            response_data = RecursiveDict(CommentedMap(**await response.json()))
        except ContentTypeError:
            response_data = {}

        if self.__variables:
            for variable in self.__variables:
                try:
                    variables[variable] = response_data[self.__variables[variable]]
                except KeyError:
                    pass

        if self.cases:
            o_connection = await self.get_case_by_id(id=str(response.status))

        if o_connection:
            await user.update_menu(context=o_connection, state="end" if not self.cases else None)

        if variables:
            await user.set_variables(variables=variables)

        return response.status, await response.text()
