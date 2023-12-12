import nest_asyncio
import pytest
from mautrix.types import ImageInfo, MediaMessageEventContent, MessageType, TextMessageEventContent

from menuflow.nodes import Input

nest_asyncio.apply()


class TestInputNode:
    def test_variable(self, input_text: Input):
        assert input_text.variable == "route.has_cats"

    def test_input_type(self, input_text: Input):
        assert input_text.input_type == MessageType.TEXT

    def test_inactivity_options(self, input_text: Input):
        assert input_text.inactivity_options == {
            "chat_timeout": 20,
            "warning_message": "Please enter an option, or the menu will end.",
            "time_between_attempts": 10,
            "attempts": 3,
        }

    @pytest.mark.asyncio
    async def test_input_text_in_text_input_node(self, input_text: Input):
        await input_text.input_text(
            content=TextMessageEventContent(msgtype=MessageType.TEXT, body="y")
        )
        assert input_text.room.route.node_id == "input-2"
        await input_text.input_text(
            content=TextMessageEventContent(msgtype=MessageType.TEXT, body="n")
        )
        assert input_text.room.route.node_id == "last-message"
        await input_text.input_text(
            content=TextMessageEventContent(msgtype=MessageType.TEXT, body="foo")
        )
        assert input_text.room.route.node_id == "last-message"

    @pytest.mark.asyncio
    async def test_input_media_in_text_input_node(self, input_text: Input):
        media_content = MediaMessageEventContent(
            msgtype=MessageType.IMAGE,
            body="foo",
            url="mxc://xyz",
            info=ImageInfo(mimetype="image/jpeg", size=29651, height=500, width=333),
        )
        await input_text.input_media(content=media_content)
        assert input_text.room.route.node_id == "last-message"

    @pytest.mark.asyncio
    async def test_input_media_in_media_input_node(self, input_media: Input):
        media_content = MediaMessageEventContent(
            msgtype=MessageType.IMAGE,
            body="foo",
            url="mxc://xyz",
            info=ImageInfo(mimetype="image/jpeg", size=29651, height=500, width=333),
        )
        await input_media.input_media(content=media_content)
        assert input_media.room.route.node_id == "last-message"
        await input_media.input_media(content=MediaMessageEventContent())
        assert input_media.room.route.node_id == "input-3"
