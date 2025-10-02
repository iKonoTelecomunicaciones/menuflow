from __future__ import annotations

import base64
from io import BytesIO
from typing import Dict

from mautrix.api import MediaPath, Method
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
from mautrix.util import magic
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


class Media(Message):
    media_cache: Dict[str, MediaMessageEventContent] = {}

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

    async def get_content_uri(self, data: bytes) -> str:
        """
        Upload the media to synapse and get the mxc from synapse
        Parameters
        ----------
        data: bytes
            The data containing the ids of the media that whatsapp cloud api returns
        Returns
        -------
            The mxc url of the media
        """
        # Upload the message media to Matrix
        path = MediaPath.v1.create
        method = Method.POST
        mime_type = None
        headers = {}

        if isinstance(data, bytes):
            mime_type = magic.mimetype(data)

        if mime_type:
            headers["Content-Type"] = mime_type

        response = await self.room.matrix_client.api.request(
            method, path, content=data, headers=headers
        )
        attachment = response.get("content_uri")

        return attachment

    async def get_media_url(self, data: bytes) -> tuple[str, str]:
        """
        Upload the media to synapse and get the mxc from synapse
        Parameters
        ----------
        data: bytes
            The data containing the ids of the media that whatsapp cloud api returns
        Returns
        -------
            The mxc url of the media and the type of the media
        """
        headers = {}
        if isinstance(data, bytes):
            message_type = magic.mimetype(data)
            headers["Content-Type"] = message_type

        attachment = await self.get_content_uri(data)
        server_name, media_matrix_id = self.room.matrix_client.api.parse_mxc_uri(attachment)
        path = MediaPath.v3.upload[server_name][media_matrix_id]
        method = Method.PUT
        await self.room.matrix_client.api.request(method, path, content=data, headers=headers)

        return attachment, message_type

    async def load_media(self) -> MediaMessageEventContent:
        """It downloads the media from the URL, uploads it to the Matrix server,
        and returns a MediaMessageEventContent object with the URL of the uploaded media

        Returns
        -------
            MediaMessageEventContent

        """
        resp = await self.session.get(self.url)
        if resp.headers.get("Content-Type") in (
            "application/json",
            "application/text",
            "application/octet-stream",
        ):
            if resp.headers.get("Content-Type") == "application/octet-stream":
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

        try:
            mxc, media_type = await self.get_media_url(data)
        except MUnknown as e:
            self.log.exception(f"error {e}")
            return
        except Exception as e:
            self.log.exception(f"Message not receive :: error {e}")
            return

        media_name = ""

        if media_type:
            ext = media_type.split("/")[-1]
            media_name = f"{self.text}.{ext}"

        return MediaMessageEventContent(
            msgtype=self.message_type, body=media_name, url=mxc, info=media_info
        )

    async def run(self):
        """It sends a message to the room with the media attached"""
        self.log.debug(f"Room {self.room.room_id} enters media node {self.id}")

        o_connection = await self.get_o_connection()
        try:
            media_message = self.media_cache[self.url]

            ext = media_message.body.split(".")[-1] if "." in media_message.body else ""
            if media_message.body != f"{self.text}.{ext}":
                media_message.body = f"{self.text}.{ext}"
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
