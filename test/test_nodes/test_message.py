import nest_asyncio
import pytest
from asyncmock import AsyncMock
from mautrix.types import MessageType
from pytest_mock import MockerFixture

from menuflow.nodes import Message
from menuflow.room import RoomState

nest_asyncio.apply()


class TestMessageNode:
    def test_message_type(self, message: Message):
        assert message.message_type == MessageType.TEXT

    def test_text(self, message: Message):
        assert message.text.strip() == "Hello, this a flow sample."

    @pytest.mark.asyncio
    async def test_text_with_variable(self, message: Message):
        await message.room.set_variable("foo", "The foo message")
        assert message.text == "Hello, this a flow sample. The foo message"

    def test_o_connection(self, message: Message):
        assert message.o_connection == "input-1"

    @pytest.mark.asyncio
    async def test_update_node(self, message: Message):
        assert message.room.node_id == message.id
        await message._update_node()
        assert message.room.node_id == message.o_connection

    @pytest.mark.asyncio
    async def test_update_node_to_end(self, message: Message):
        del message.content["o_connection"]
        await message._update_node()
        assert message.room.node_id == ""
        assert message.room.state == RoomState.END

    @pytest.mark.asyncio()
    async def test_run(self, message: Message, mocker: MockerFixture):
        async_mock = AsyncMock()
        mock_func = mocker.patch.object(Message, "send_message", side_effect=async_mock)
        await message.run()
        assert mock_func.called == True
