from typing import Dict, Tuple

from aiohttp import ClientTimeout, ContentTypeError, FormData
from mautrix.util.config import RecursiveDict
from ruamel.yaml.comments import CommentedMap

from ..nodes import Base
from ..repository import TTMMiddleware as TTMMiddlewareModel
from ..room import Room


class TTMMiddleware(Base):
    def __init__(self, ttm_data: TTMMiddlewareModel, room: Room, default_variables: Dict) -> None:
        Base.__init__(self, room=room, default_variables=default_variables)
        self.log = self.log.getChild(ttm_data.id)
        self.content: TTMMiddlewareModel = ttm_data

    @property
    def method(self) -> str:
        return self.content.method

    @property
    def url(self) -> str:
        return self.render_data(self.content.url)

    @property
    def variables(self) -> Dict:
        return self.render_data(self.content.variables)

    @property
    def cookies(self) -> Dict:
        return self.render_data(self.content.cookies)

    @property
    def headers(self) -> Dict:
        return self.render_data(self.content.headers)

    @property
    def basic_auth(self) -> Dict:
        return self.render_data(self.content.basic_auth)

    @property
    def target_language(self) -> str:
        return self.render_data(self.content.target_language)

    @property
    def source_language(self) -> str:
        return self.render_data(self.content.source_language)

    @property
    def provider(self) -> str:
        return self.render_data(self.content.provider)

    async def run(self, text: str) -> Tuple[int, str]:
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

        if self.headers:
            request_body["headers"] = self.headers

        data = FormData()
        data.add_field(name="text", value=text)
        data.add_field(name="target_language", value=self.target_language)
        data.add_field(name="source_language", value=self.source_language)
        data.add_field(name="provider", value=self.provider)
        request_body["data"] = data

        try:
            timeout = ClientTimeout(total=self.config["menuflow.timeouts.middlewares"])
            response = await self.session.request(
                self.method, self.url, timeout=timeout, **request_body
            )
        except Exception as e:
            self.log.exception(f"Error in middleware: {e}")
            return

        variables = {}

        if self.cookies:
            for cookie in self.cookies:
                variables[cookie] = response.cookies.output(cookie)

        self.log.debug(
            f"middleware: {self.id}  type: {self.type} method: {self.method} "
            f"url: {self.url} status: {response.status}"
        )

        try:
            response_data = await response.json()
        except ContentTypeError:
            response_data = await response.text()

        self.log.info(f"response_data: {response_data}")

        if isinstance(response_data, dict):
            # Tulir and its magic since time immemorial
            serialized_data = RecursiveDict(CommentedMap(**response_data))
            if self.variables:
                for variable in self.variables:
                    try:
                        variables[variable] = self.render_data(
                            serialized_data[self.variables[variable]]
                        )
                    except KeyError:
                        pass
        elif isinstance(response_data, str):
            if self.variables:
                for variable in self.variables:
                    try:
                        variables[variable] = self.render_data(response_data)
                    except KeyError:
                        pass

                    break

        if variables:
            await self.room.set_variables(variables=variables)

        return response.status, response_data.get("text")
