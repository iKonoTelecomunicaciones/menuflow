from __future__ import annotations

import mimetypes
from io import BytesIO
from typing import Dict

from mautrix.errors import MUnknown
from mautrix.types import (
    AudioInfo,
    FileInfo,
    ImageInfo,
    MediaMessageEventContent,
    MessageType,
    VideoInfo,
)
from mautrix.util.magic import mimetype

from ..db.room import RoomState
from ..repository import Media as MediaModel
from .message import Message

try:
    from PIL import Image
except ImportError:
    Image = None


class Media(Message):

    media_cache: Dict[str, MediaMessageEventContent] = {}

    def __init__(self, media_node_data: MediaModel) -> None:
        Message.__init__(self, media_node_data)
        self.log = self.log.getChild(media_node_data.get("id"))
        self.data: Dict = media_node_data

    @property
    def url(self) -> str:
        return self.render_data(self.data.get("url", ""))

    @property
    def info(self) -> ImageInfo | VideoInfo | AudioInfo | FileInfo:
        if MessageType.AUDIO == self.message_type:
            media_info = AudioInfo(**self.render_data(self.data.get("info", {})))
        elif MessageType.VIDEO == self.message_type:
            media_info = VideoInfo(**self.render_data(self.data.get("info", {})))
        elif MessageType.IMAGE == self.message_type:
            media_info = ImageInfo(**self.render_data(self.data.get("info", {})))
        elif MessageType.FILE == self.message_type:
            media_info = FileInfo(**self.render_data(self.data.get("info", {})))
        else:
            return

        return media_info

    async def load_media(self) -> MediaMessageEventContent:
        """It downloads the media from the URL, uploads it to the Matrix server,
        and returns a MediaMessageEventContent object with the URL of the uploaded media

        Returns
        -------
            MediaMessageEventContent

        """
        resp = await self.session.get(self.url)
        data = await resp.read()
        media_info = self.info

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
            mxc = await self.matrix_client.upload_media(
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

        try:
            media_message = self.media_cache[self.url]
        except KeyError:
            media_message = await self.load_media()
            self.media_cache[self.url] = media_message

        await self.matrix_client.send_message(room_id=self.room.room_id, content=media_message)

        await self.room.update_menu(
            node_id=self.o_connection,
            state=RoomState.END if not self.o_connection else None,
        )
