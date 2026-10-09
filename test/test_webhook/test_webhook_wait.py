import asyncio

import pytest

from menuflow.db.route import RouteState
from menuflow.utils.types import QueueSignal, Scopes

pytestmark = pytest.mark.asyncio

SHORT_TIMEOUT = 0.05


def _deadline(node) -> float:
    return node.room.scope.get(Scopes.NODE)["inactivity"]["start_ttl"]


class TestWebhookWait:
    async def test_wait_times_out_and_sets_timeout_state(self, story, matrix):
        """Without messages, the wait expires and the route remains in TIMEOUT."""
        node = await story.room()
        node.content["inactivity_options"]["chat_timeout"] = SHORT_TIMEOUT
        node.room.route.state = RouteState.INPUT

        result = await matrix.get_input_response(room=node.room, node=node)

        assert result is QueueSignal.TIMEOUT
        assert node.room.route.state == RouteState.TIMEOUT

    async def test_wait_returns_webhook_payload(self, story, matrix):
        """An event that enters the queue during the wait is returned as is."""
        node = await story.room()
        node.content["inactivity_options"]["chat_timeout"] = 1
        payload = {"user_id": "S1", "status": "ok"}

        waiting = asyncio.create_task(matrix.get_input_response(room=node.room, node=node))
        await asyncio.sleep(0.01)
        matrix.QUEUE_MESSAGE[node.room.room_id].put_nowait(payload)

        assert await waiting == payload

    async def test_invalid_text_does_not_restart_deadline(self, story, matrix):
        """After a message, the saved deadline does not change and the next wait uses the rest."""
        node = await story.room()
        node.content["inactivity_options"]["chat_timeout"] = SHORT_TIMEOUT

        waiting = asyncio.create_task(matrix.get_input_response(room=node.room, node=node))
        await asyncio.sleep(0.01)
        deadline = _deadline(node)
        matrix.QUEUE_MESSAGE[node.room.room_id].put_nowait("hola")
        assert await waiting == "hola"
        assert _deadline(node) == deadline

        result = await matrix.get_input_response(room=node.room, node=node)

        assert result is QueueSignal.TIMEOUT
        assert _deadline(node) == deadline

    async def test_no_chat_timeout_does_not_wait(self, story, matrix):
        """Without chat_timeout the wait ends immediately."""
        node = await story.room()
        node.content["inactivity_options"] = {}

        result = await matrix.get_input_response(room=node.room, node=node)

        assert result is None
