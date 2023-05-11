from typing import Dict, Tuple

from aiohttp import ClientTimeout, ContentTypeError
from mautrix.util.config import RecursiveDict
from ruamel.yaml.comments import CommentedMap

from ..nodes import Base
from ..repository import HTTPMiddleware as HTTPMiddlewareModel
from ..room import Room


class HTTPMiddleware(Base):
    room: Room = None

    def __init__(self, http_middleware_data: HTTPMiddlewareModel) -> None:
        self.log = self.log.getChild(http_middleware_data.get("id"))
        self.content: Dict = http_middleware_data

    @property
    def url(self) -> str:
        return self.render_data(self.content.get("url", ""))

    @property
    def token_type(self) -> str:
        return self.render_data(self.content.get("token_type", ""))

    @property
    def auth(self) -> Dict:
        return self.render_data(self.content.get("auth", {}))

    @property
    def general(self) -> Dict:
        return self.render_data(self.content.get("general", {}))

    @property
    def token_url(self) -> str:
        complete_url = f"{self.url}{self.auth.get('token_path')}"
        return self.render_data(complete_url)

    @property
    def attempts(self) -> int:
        return int(self.auth.get("attempts", 2))

    @property
    def middleware_variables(self) -> Dict:
        return self.render_data(self.auth.get("variables", {}))

    @property
    def method(self) -> Dict:
        return self.render_data(self.auth.get("method", ""))

    @property
    def cookies(self) -> Dict:
        return self.render_data(self.auth.get("cookies", {}))

    @property
    def headers(self) -> Dict:
        return self.render_data(self.auth.get("headers", {}))

    @property
    def query_params(self) -> Dict:
        return self.render_data(self.auth.get("query_params", {}))

    @property
    def data(self) -> Dict:
        return self.render_data(self.auth.get("data", {}))

    @property
    def json(self) -> Dict:
        return self.render_data(self.auth.get("json", {}))

    @property
    def basic_auth(self) -> Dict:
        return self.render_data(self.auth.get("basic_auth", {}))

    async def auth_request(self) -> Tuple[int, str]:
        """Make the auth request to refresh api token

        Parameters
        ----------
        session : ClientSession
            ClientSession

        Returns
        -------
            The status code and the response text.

        """

        request_body = {}

        if self.query_params:
            request_body["params"] = self.query_params

        if self.headers:
            request_body["headers"] = self.headers

        if self.data:
            request_body["data"] = self.data

        if self.json:
            request_body["json"] = self.json

        try:
            timeout = ClientTimeout(total=self.config["menuflow.timeouts.middlewares"])
            response = await self.session.request(
                self.method, self.token_url, timeout=timeout, **request_body
            )
        except Exception as e:
            self.log.exception(f"Error in middleware: {e}")
            return

        variables = {}

        if self.cookies:
            for cookie in self.cookies:
                variables[cookie] = response.cookies.output(cookie)

        self.log.debug(
            f"middleware: {self.id}  type: {self.type} method: {self.method} url: {self.token_url} status: {response.status}"
        )

        try:
            response_data = await response.json()
        except ContentTypeError:
            response_data = {}

        if isinstance(response_data, dict):
            # Tulir and its magic since time immemorial
            serialized_data = RecursiveDict(CommentedMap(**response_data))
            if self.middleware_variables:
                for variable in self.middleware_variables:
                    try:
                        variables[variable] = self.render_data(
                            serialized_data[self.middleware_variables[variable]]
                        )
                    except KeyError:
                        pass
        elif isinstance(response_data, str):
            if self.middleware_variables:
                for variable in self.middleware_variables:
                    try:
                        variables[variable] = self.render_data(response_data)
                    except KeyError:
                        pass

                    break

        if variables:
            await self.room.set_variables(variables=variables)

        return response.status, await response.text()
