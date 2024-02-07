from typing import Dict, Tuple

from aiohttp import ClientTimeout, ContentTypeError, FormData
from mautrix.util.config import RecursiveDict
from ruamel.yaml.comments import CommentedMap

from ..nodes import Base
from ..repository import IRMMiddleware as IRMMiddlewareModel
from ..room import Room


class IRMMiddleware(Base):
    def __init__(self, irm_data: IRMMiddlewareModel, room: Room, default_variables: Dict) -> None:
        Base.__init__(self, room=room, default_variables=default_variables)
        self.log = self.log.getChild(irm_data.id)
        self.content: IRMMiddlewareModel = irm_data

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
    def prompt(self) -> str:
        return self.render_data(self.content.prompt)

    async def run(self, image_mxc: str, content_type: str, filename: str) -> Tuple[int, str]:
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
        image = await self.room.matrix_client.download_media(url=image_mxc)
        data.add_field(name="image", value=image, content_type=content_type, filename=filename)
        data.add_field(name="prompt", value=self.prompt)
        if self.content.additional_arguments:
            additional_arguments: Dict = self.content.additional_arguments.serialize()
            for key, value in additional_arguments.items():
                data.add_field(name=key, value=value)
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

        self.log.critical(f"response_data: {response_data}")

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

        return response.status, await response.text()
