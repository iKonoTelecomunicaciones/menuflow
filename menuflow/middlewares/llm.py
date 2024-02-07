from typing import Dict, Tuple

from aiohttp import ClientTimeout, ContentTypeError, FormData
from mautrix.util.config import RecursiveDict
from ruamel.yaml.comments import CommentedMap

from ..nodes import Base
from ..repository import LLMMiddleware as LLMMiddlewareModel
from ..room import Room


class LLMMiddleware(Base):
    def __init__(self, llm_data: LLMMiddlewareModel, room: Room, default_variables: Dict) -> None:
        Base.__init__(self, room=room, default_variables=default_variables)
        self.log = self.log.getChild(llm_data.id)
        self.content: LLMMiddlewareModel = llm_data

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

    @property
    def provider(self) -> str:
        return self.render_data(self.content.provider)

    @property
    def args(self) -> Dict:
        return self.render_data(self.content.args)

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
        question = text

        if self.headers:
            request_body["headers"] = self.headers

        if self.args:
            args_values = self.args.values()
            question = f"{text}, {', '.join(args_values)}"

        data = {
            "prompt": self.prompt,
            "question": question,
            "provider": self.provider,
        }
        if self.content.additional_arguments:
            additional_arguments: Dict = self.content.additional_arguments.serialize()
            for key, value in additional_arguments.items():
                data[key] = value = value
        request_body["json"] = data

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
