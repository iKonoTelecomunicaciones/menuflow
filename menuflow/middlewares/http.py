from __future__ import annotations

from typing import Any, Dict, Tuple

from aiohttp import ClientSession, ContentTypeError
from attr import dataclass, ib
from jinja2 import Template
from mautrix.types import SerializableAttrs
from mautrix.util.config import RecursiveDict
from ruamel.yaml.comments import CommentedMap

from ..nodes.flow_object import FlowObject


@dataclass
class Auth(SerializableAttrs):
    method: str = ib(default=None, metadata={"json": "method"})
    token_path: str = ib(default=None, metadata={"json": "token_path"})
    headers: Dict[str, Any] = ib(default=None, metadata={"json": "headers"})
    cookies: Dict[str, Any] = ib(metadata={"json": "cookies"}, factory=dict)
    data: Dict[str, Any] = ib(default=None, metadata={"json": "data"})
    query_params: Dict[str, Any] = ib(default=None, metadata={"json": "query_params"})
    variables: Dict[str, Any] = ib(default=None, metadata={"json": "variables"})
    token_path: str = ib(default=None, metadata={"json": "token_path"})
    basic_auth: Dict[str, Any] = ib(default=None, metadata={"json": "basic_auth"})


@dataclass
class General(SerializableAttrs):
    headers: Dict[str, Any] = ib(default=None, metadata={"json": "headers"})


@dataclass
class HTTPMiddleware(FlowObject):

    url: str = ib(default=None, metadata={"json": "url"})
    token_type: str = ib(default=None, metadata={"json": "token_type"})
    auth: Auth = ib(default=None, metadata={"json": "auth"})
    general: General = ib(default=None, metadata={"json": "general"})

    @property
    def _url(self) -> Template:
        return self.render_data(self.url)

    @property
    def _token_url(self) -> Template:
        complete_url = f"{self.url}{self.auth.token_path}"
        return self.render_data(complete_url)

    @property
    def _token_type(self) -> Template:
        return self.render_data(self.token_type)

    @property
    def _variables(self) -> Template:
        return self.render_data(self.serialize()["auth"]["variables"])

    @property
    def _cookies(self) -> Template:
        return self.render_data(self.serialize()["auth"]["cookies"])

    @property
    def _headers(self) -> Dict[str, Template]:
        return self.render_data(self.serialize()["auth"]["headers"])

    @property
    def _query_params(self) -> Dict[str, Template]:
        return self.render_data(self.serialize()["auth"]["query_params"])

    @property
    def _data(self) -> Dict[str, Template]:
        return self.render_data(self.serialize()["auth"]["data"])

    @property
    def _basic_auth(self) -> Dict[str, Template]:
        return self.render_data(self.serialize()["auth"]["basic_auth"])

    @property
    def _general_headers(self) -> Dict[str, Template]:
        return self.render_data(self.serialize()["general"]["headers"])

    async def auth_request(self, session: ClientSession) -> Tuple[int, str]:

        request_body = {}

        if self.auth.query_params:
            request_body["params"] = self._query_params

        if self.auth.headers:
            request_body["headers"] = self._headers

        if self.auth.data:
            request_body["json"] = self._data

        try:
            response = await session.request(self.auth.method, self._token_url, **request_body)
        except Exception as e:
            self.log.exception(f"Error: {e}")

        variables = {}

        if self.auth.cookies:
            for cookie in self._cookies:
                variables[cookie] = response.cookies.output(cookie)

        self.log.debug(
            f"middleware: {self.id} method: {self.auth.method} url: {self._token_url} status: {response.status}"
        )

        try:
            response_data = await response.json()
        except ContentTypeError:
            response_data = {}

        if isinstance(response_data, dict):
            # Tulir and its magic since time immemorial
            serialized_data = RecursiveDict(CommentedMap(**response_data))
            if self._variables:
                for variable in self._variables:
                    try:
                        variables[variable] = self.render_data(
                            serialized_data[self._variables[variable]]
                        )
                    except KeyError:
                        pass
        elif isinstance(response_data, str):
            if self._variables:
                for variable in self._variables:
                    try:
                        variables[variable] = self.render_data(response_data)
                    except KeyError:
                        pass

                    break

        if variables:
            await self.room.set_variables(variables=variables)

        return response.status, await response.text()
