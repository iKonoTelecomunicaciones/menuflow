from typing import Dict, Tuple

from aiohttp import ClientTimeout, ContentTypeError, FormData
from mautrix.util.config import RecursiveDict
from ruamel.yaml.comments import CommentedMap

from ..nodes import Base
from ..repository import ASRMiddleware as ASRMiddlewareModel
from ..room import Room


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
        return self.render_data(self.content.url)

    @property
    def headers(self) -> Dict:
        return self.render_data(self.content.headers)

    @property
    def middleware_variables(self) -> Dict:
        return self.render_data(self.content.variables)

    @property
    def method(self) -> Dict:
        return self.render_data(self.content.method)

    @property
    def cookies(self) -> Dict:
        return self.render_data(self.content.cookies)

    @property
    def provider(self) -> str:
        return self.render_data(self.content.provider)

    @property
    def target_languages(self) -> str:
        return self.render_data(self.content.target_languages)

    @property
    def source_language(self) -> str:
        return self.render_data(self.content.source_language)

    async def run(self, audio_url: str, audio_name: str = None) -> Tuple[int, str]:
        audio = await self.room.matrix_client.download_media(url=audio_url)
        result = await self.http_request(audio=audio, audio_name=audio_name)

        return result

    async def http_request(self, audio, audio_name) -> Tuple[int, str]:
        """Recognize the text and return the status code and the text."""
        request_body = {}

        if self.headers:
            request_body["headers"] = self.headers

        if not audio:
            self.log.error("Error getting the audio")
            return

        form_data = FormData()
        form_data.add_field("audio", audio, filename=audio_name, content_type="audio/ogg")
        form_data.add_field("provider", self.provider)

        if self.target_languages and self.source_language:
            form_data.add_field("target_languages", self.target_languages)
            form_data.add_field("source_language", self.source_language)

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

        result_text = (
            response_data["result"].get(self.target_languages)
            if self.target_languages
            else response_data.get("text")
        )

        return response.status, result_text
