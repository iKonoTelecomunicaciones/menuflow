from __future__ import annotations

from json import dumps
from typing import Dict, Tuple

from aiohttp import BasicAuth, ClientSession
from aiohttp.client_exceptions import ContentTypeError
from attr import dataclass, ib
from jinja2 import Template
from mautrix.util.config import RecursiveDict
from ruamel.yaml.comments import CommentedMap

from ..jinja.jinja_template import jinja_env
from .switch import Switch


@dataclass
class HTTPRequest(Switch):
    method: str = ib(default=None, metadata={"json": "method"})
    url: str = ib(default=None, metadata={"json": "url"})
    variables: Dict = ib(metadata={"json": "variables"}, factory=dict)
    cookies: Dict = ib(metadata={"json": "cookies"}, factory=dict)
    query_params: Dict = ib(metadata={"json": "query_params"}, factory=dict)
    headers: Dict = ib(metadata={"json": "headers"}, factory=dict)
    basic_auth: Dict = ib(metadata={"json": "basic_auth"}, factory=dict)
    data: Dict = ib(metadata={"json": "data"}, factory=dict)

    @property
    def _url(self) -> Template:
        return self.render_data(self.url)

    @property
    def _variables(self) -> Template:
        return self.render_data(self.serialize()["variables"])

    @property
    def _cookies(self) -> Template:
        return self.render_data(self.serialize()["cookies"])

    @property
    def _headers(self) -> Dict[str, Template]:
        return self.render_data(self.serialize()["headers"])

    @property
    def _auth(self) -> Dict[str, Template]:
        return self.render_data(self.serialize()["basic_auth"])

    @property
    def _query_params(self) -> Dict:
        return self.render_data(self.serialize()["query_params"])

    @property
    def _data(self) -> Dict:
        return self.render_data(self.serialize()["data"])

    async def request(self, session: ClientSession) -> Tuple(int, str):

        request_body = {}

        if self.query_params:
            request_body["params"] = self._query_params

        # if self.basic_auth:
        #     request_body["auth"] = BasicAuth(
        #         self._render(self._auth, self.user._variables)["login"],
        #         self._render(self._auth, self.user._variables)["password"],
        #     )

        if self.headers:
            request_body["auth"] = self._headers

        if self.data:
            request_body["json"] = self._data

        response = await session.request(self.method, self._url, **request_body)

        variables = {}
        o_connection = None

        if self._cookies:
            for cookie in self._cookies:
                variables[cookie] = response.cookies.output(cookie)

        self.log.debug(
            f"node: {self.id} method: {self.method} url: {self.url} status: {response.status}"
        )

        # Tulir and its magic since time immemorial
        try:
            response_data = RecursiveDict(CommentedMap(**await response.json()))
        except ContentTypeError:
            response_data = {}

        if self._variables:
            self.log.debug(self._variables)
            for variable in self._variables:
                # self.log.debug(variable)
                # self.log.debug(self._variables[variable])
                # self.log.debug(response_data.__dict__)
                # self.log.debug(response_data["tipomensaje"])
                try:
                    variables[variable] = response_data[self.variables[variable]]
                except KeyError:
                    pass

        if self.cases:
            o_connection = await self.get_case_by_id(id=str(response.status))

        if o_connection:
            await self.user.update_menu(
                node_id=o_connection, state="end" if not self.cases else None
            )

        if variables:
            await self.user.set_variables(variables=variables)

        return response.status, await response.text()
