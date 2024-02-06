from typing import Dict, Tuple

from aiohttp import ClientTimeout, ContentTypeError, FormData
from ..nodes import Base
from ..repository import ASRMiddlewareModel
from ..room import Room
from mautrix.util.config import RecursiveDict
from ruamel.yaml.comments import CommentedMap
class ASRMiddleware(Base):
    def __init__(
        self,
        asr_middleware_content: ASRMiddlewareModel,
        room: Room,
        default_variables: Dict,
    ) -> None:
        Base.__init__(self, room=room, default_variables=default_variables)
        self.log = self.log.getChild(asr_middleware_content.id)
        self.content: ASRMiddlewareModel = asr_middleware_content

    @property
    def url(self) -> str:
        return self.render_data(self.content.get("url", ""))

    @property
    def headers(self) -> Dict:
        return self.render_data(self.content.get("general", {}).get("headers", {})) 

    @property
    def middleware_variables(self) -> Dict:
        return self.render_data(self.content.get("variables", {}))

    @property
    def data(self) -> Dict:
        return self.render_data(self.content.get("data", {}))

    @property
    def json(self) -> Dict:
        return self.render_data(self.content.get("json", {}))

    @property
    def method(self) -> Dict:
        return self.render_data(self.content.get("method", ""))

    @property
    def cookies(self) -> Dict:
        return self.render_data(self.content.get("cookies", {}))

    @property
    def query_params(self) -> Dict:
        return self.render_data(self.content.get("query_params", {}))

    @property
    def provider(self) -> str:
        return self.render_data(self.content.get("provider", {}))

    async def run(self, extended_data: Dict, audio_url: str):
        audio = await self.room.matrix_client.download_media(url=audio_url)
        result = await self.http_request(audio=audio)

        return result

    async def http_request(self, audio) -> Tuple[int, str]:
        """Recognize the text and return the status code and the text."""
        request_body = {}
        form_data = FormData()

        if self.query_params:
            request_body["params"] = self.query_params

        if self.headers:
            request_body["headers"] = self.headers

        if audio:
            form_data.add_field("audio", audio, filename="audio.ogg", content_type="audio/ogg")
            form_data.add_field("provider", self.provider)
        else:
            self.log.error("Error getting the audio")
            return

        if self.json:
            request_body["json"] = self.json

        try:
            timeout = ClientTimeout(total=self.config["menuflow.timeouts.middlewares"])
            response = await self.session.request(
                self.method,
                self.url,
                timeout=timeout,
                data=form_data,
                **request_body,
            )
        except Exception as e:
            self.log.exception(f"Audio to text conversion error: {e}")
            return

        variables = {}

        if self.cookies:
            for cookie in self.cookies:
                variables[cookie] = response.cookies.output(cookie)

        try:
            response_data = await response.json()
        except ContentTypeError:
            response_data = {}

        if not response_data:
            return response.status, None

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
