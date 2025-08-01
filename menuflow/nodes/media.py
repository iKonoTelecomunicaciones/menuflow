from __future__ import annotations

import base64
import mimetypes
from io import BytesIO
from typing import TYPE_CHECKING, Dict

from mautrix.errors import MUnknown
from mautrix.types import (
    AudioInfo,
    FileInfo,
    ImageInfo,
    MediaInfo,
    MediaMessageEventContent,
    MessageType,
    VideoInfo,
)
from mautrix.util.magic import mimetype

from ..db.route import RouteState
from ..events import MenuflowNodeEvents
from ..events.event_generator import send_node_event
from ..repository import Media as MediaModel
from ..room import Room
from ..utils import Nodes
from .message import Message

try:
    from PIL import Image
except ImportError:
    Image = None


if TYPE_CHECKING:
    from ..middlewares import HTTPMiddleware


class Media(Message):
    media_cache: Dict[str, MediaMessageEventContent] = {}

    middleware: "HTTPMiddleware" = None

    def __init__(self, media_node_data: MediaModel, room: Room, default_variables: Dict) -> None:
        Message.__init__(self, media_node_data, room=room, default_variables=default_variables)
        self.log = self.log.getChild(media_node_data.get("id"))
        self.content: Dict = media_node_data

    @property
    def url(self) -> str:
        return self.render_data(self.content.get("url", ""))

    @property
    def info(self) -> MediaInfo:
        if MessageType.AUDIO == self.message_type:
            media_info = AudioInfo(**self.render_data(self.content.get("info", {})))
        elif MessageType.VIDEO == self.message_type:
            media_info = VideoInfo(**self.render_data(self.content.get("info", {})))
        elif MessageType.IMAGE == self.message_type:
            media_info = ImageInfo(**self.render_data(self.content.get("info", {})))
        elif MessageType.FILE == self.message_type:
            media_info = FileInfo(**self.render_data(self.content.get("info", {})))
        else:
            self.log.warning(
                f"It has not been possible to identify the message type of the node {self.id}"
            )
            return

        return media_info

    @property
    def context_params(self) -> dict[str, str]:
        return self.render_data(
            {
                "bot_mxid": "{{ route.bot_mxid }}",
                "customer_room_id": "{{ route.customer_room_id }}",
            }
        )

    async def load_media(self) -> MediaMessageEventContent:
        """It downloads the media from the URL, uploads it to the Matrix server,
        and returns a MediaMessageEventContent object with the URL of the uploaded media

        Returns
        -------
            MediaMessageEventContent

        """
        if self.middleware:
            self.middleware.room = self.room
            request_params_ctx = self.context_params
            request_params_ctx.update({"middleware": self.middleware})
        else:
            request_params_ctx = {}

        resp = await self.session.get(self.url, trace_request_ctx=request_params_ctx)
        content_type = resp.headers.get("Content-Type", "").lower()

        self.log.debug(
            f"node: {self.id} type: media url: {self.url} status: {resp.status} content_type: {content_type}"
        )

        if content_type.startswith(
            ("application/json", "application/text", "application/octet-stream")
        ):
            if content_type.startswith("application/octet-stream"):
                base64_data = await resp.read()
            else:
                base64_data = await resp.text()

            try:
                data = base64.b64decode(base64_data)
            except Exception as e:
                self.log.exception(f"error {e}")
                return
        else:
            data = await resp.read()

        media_info = self.info
        if media_info is None:
            return

        if not media_info.mimetype:
            media_info.mimetype = mimetype(data)

        if (
            media_info.mimetype.startswith("image/")
            and not media_info.width
            and not media_info.height
        ):
            with BytesIO(data) as inp, Image.open(inp) as img:
                media_info.width, media_info.height = img.size

        media_info.size = len(data)

        extension = {
            "image/webp": ".webp",
            "image/jpeg": ".jpg",
            "video/mp4": ".mp4",
            "audio/mp4": ".m4a",
            "audio/ogg": ".ogg",
            "application/pdf": ".pdf",
        }.get(media_info.mimetype)

        extension = extension or mimetypes.guess_extension(media_info.mimetype) or ""

        file_name = f"{self.message_type.value[2:]}{extension}" if self.message_type else None

        try:
            mxc = await self.room.matrix_client.upload_media(
                data=data, mime_type=media_info.mimetype, filename=file_name
            )
        except MUnknown as e:
            self.log.exception(f"error {e}")
            return
        except Exception as e:
            self.log.exception(f"Message not receive :: error {e}")
            return

        return MediaMessageEventContent(
            msgtype=self.message_type, body=self.text, url=mxc, info=media_info
        )

    async def run(self):
        """It sends a message to the room with the media attached"""
        self.log.debug(f"Room {self.room.room_id} enters media node {self.id}")

        o_connection = await self.get_o_connection()
        try:
            media_message = self.media_cache[self.url]

            if media_message.body != self.text:
                media_message.body = self.text
        except KeyError:
            media_message = await self.load_media()
            if media_message is None:
                await self.room.update_menu(
                    node_id=o_connection,
                    state=RouteState.END if not o_connection else None,
                )
                return
            self.media_cache[self.url] = media_message

        await self.send_message(room_id=self.room.room_id, content=media_message)

        await self.room.update_menu(
            node_id=o_connection,
            state=RouteState.END if not o_connection else None,
        )

        await send_node_event(
            config=self.room.config,
            send_event=self.content.get("send_event"),
            event_type=MenuflowNodeEvents.NodeEntry,
            room_id=self.room.room_id,
            sender=self.room.matrix_client.mxid,
            node_type=Nodes.media,
            node_id=self.id,
            o_connection=o_connection,
            variables=self.room.all_variables | self.default_variables,
        )
