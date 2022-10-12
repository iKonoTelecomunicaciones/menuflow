from __future__ import annotations

from typing import Dict, Tuple

from aiohttp import BasicAuth, ClientSession
from attr import dataclass, ib
from jinja2 import Template
from ruamel.yaml.comments import CommentedMap

from mautrix.util.config import RecursiveDict

from ..user import User
from .input import Input


@dataclass
class HTTPRequest(Input):
    method: str = ib(default=None, metadata={"json": "method"})
    url: str = ib(default=None, metadata={"json": "url"})
    variables: Dict = ib(metadata={"json": "variables"}, factory=dict)
    cookies: Dict = ib(metadata={"json": "cookies"}, factory=dict)
    query_params: Dict = ib(metadata={"json": "query_params"}, factory=dict)
    headers: Dict = ib(metadata={"json": "headers"}, factory=dict)
    basic_auth: Dict = ib(metadata={"json": "basic_auth"}, factory=dict)
    data: Dict = ib(metadata={"json": "data"}, factory=dict)

    @property
    def _headers(self) -> Dict[str, Template]:
        return {header: Template(self.headers[header]) for header in self.headers}

    @property
    def _auth(self) -> Dict[str, Template]:
        return {item: Template(self.basic_auth[item]) for item in self.basic_auth.__dict__}

    @property
    def _query_params(self) -> Dict:
        return {
            query_param: Template(self.query_params[query_param])
            for query_param in self.query_params
        }

    @property
    def _data(self) -> Dict:
        if self.data:
            return {value: Template(self.data[value]) for value in self.data.__dict__}

    @property
    def _url(self) -> Template:
        return Template(self.url)

    def _render(self, templates: Dict[str, Template], variables: Dict) -> Dict:
        if not templates:
            return
        try:
            return {item: templates[item].render(**variables) for item in templates}
        except Exception as e:
            self.log.exception(e)

    async def request(self, user: User, session: ClientSession) -> Tuple[str, Dict]:

        request_body = {}

        if self.query_params:
            request_body["params"] = self._render(self._query_params, user._variables)

        if self.basic_auth:
            request_body["auth"] = BasicAuth(
                self._render(self._auth, user._variables)["login"],
                self._render(self._auth, user._variables)["password"],
            )

        if self.headers:
            request_body["auth"] = self._render(self._headers, user._variables)

        if self.data:
            request_body["json"] = (self._render(self._data, user._variables),)

        response = await session.request(
            self.method, self._url.render(**user._variables), **request_body
        )

        variables = {}
        o_connection = None

        if self.cookies:
            for cookie in self.cookies.__dict__:
                variables[cookie] = response.cookies.output(cookie)

        try:
            # Tulir and its magic since time immemorial
            response_data = RecursiveDict(CommentedMap(**await response.json()))
            if self.variables:
                for variable in self.variables.__dict__:
                    try:
                        variables[variable] = response_data[self.variables[variable]]
                    except TypeError:
                        pass
        except Exception as e:
            self.log.exception(e)

        if self.cases:
            o_connection = await self.get_case_by_id(id=str(response.status))

        if o_connection:
            await user.update_menu(context=o_connection)

        if variables:
            await user.set_variables(variables=variables)
