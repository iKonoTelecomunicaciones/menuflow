import asyncio
import json
import logging
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from mautrix.types import EventType, MessageEvent, MessageType, TextMessageEventContent

from menuflow.config import Config
from menuflow.db.route import Route, RouteState
from menuflow.db.webhook import Webhook as DBWebhook
from menuflow.db.webhook_queue import WebhookQueue as DBWebhookQueue
from menuflow.matrix import MatrixHandler
from menuflow.nodes.webhook import Webhook
from menuflow.room import Room
from menuflow.webhook.webhook import Webhook as Subscription
from menuflow.webhook.webhook_handler import WebhookHandler
from menuflow.webhook.webhook_queue import WebhookQueue

BOT_MXID = "@bot:example.com"
ROOM_ID = "!room:example.com"
SESSION_ID = "S1"

WEBHOOK_NODE = {
    "id": "webhook_0",
    "type": "webhook",
    "filter": '.user_id == "{{ route.session_id }}"',
    "variable": "route.respuesta",
    "validation": "{{ route.respuesta }}",
    "validation_fail": {"message": "Opcion invalida"},
    "variables": {"route.payload": "."},
    "inactivity_options": {"chat_timeout": 90},
    "cases": [
        {"id": "webhook", "o_connection": "on_webhook"},
        {"id": "timeout", "o_connection": "on_timeout"},
        {"id": "cancelar", "o_connection": "on_cancel"},
    ],
}


class MemoryDB:
    """Tables subscriptions and queued_events replaced in memory."""

    def __init__(self) -> None:
        self.subscriptions: list[dict] = []
        self.queued_events: list[dict] = []
        self.rooms: dict[str, Room] = {}
        self.nodes: dict[str, object] = {}
        self._next_event_id = 1

    def subscription(self, room_id: str) -> dict | None:
        return next((row for row in self.subscriptions if row["room_id"] == room_id), None)


def _queue_row(row: dict) -> SimpleNamespace:
    return SimpleNamespace(**row)


@pytest.fixture
def memory(mocker) -> MemoryDB:
    """Patches the SQL access to the subscriptions and the queued_events."""
    db = MemoryDB()

    async def insert_subscription(self) -> None:
        db.subscriptions.append(
            {
                "id": len(db.subscriptions) + 1,
                "room_id": self.room_id,
                "client": self.client,
                "filter": self.filter,
                "subscription_time": self.subscription_time,
            }
        )

    async def get_subscriptions(cls) -> list | None:
        if not db.subscriptions:
            return None
        return [
            Subscription(
                room_id=row["room_id"],
                client=row["client"],
                filter=row["filter"],
                subscription_time=row["subscription_time"],
                id=row["id"],
            )
            for row in db.subscriptions
        ]

    async def get_subscription(cls, room_id: str, client: str):
        row = next(
            (
                item
                for item in db.subscriptions
                if item["room_id"] == room_id and item["client"] == client
            ),
            None,
        )
        if row is None:
            return None
        return Subscription(
            room_id=row["room_id"],
            client=row["client"],
            filter=row["filter"],
            subscription_time=row["subscription_time"],
            id=row["id"],
        )

    async def delete_subscription(self) -> None:
        db.subscriptions[:] = [
            row
            for row in db.subscriptions
            if not (
                row["room_id"] == self.room_id
                and row["client"] == self.client
                and row["filter"] == self.filter
            )
        ]

    async def insert_event(self) -> int:
        event = self.event if isinstance(self.event, str) else json.dumps(self.event)
        row = {
            "id": db._next_event_id,
            "event": event,
            "ending_time": self.ending_time,
            "creation_time": self.creation_time,
        }
        db._next_event_id += 1
        db.queued_events.append(row)
        return row["id"]

    async def get_events(cls) -> list | None:
        if not db.queued_events:
            return None
        return [_queue_row(row) for row in reversed(db.queued_events)]

    async def get_event(cls, event: dict):
        encoded = json.dumps(event)
        row = next((item for item in db.queued_events if item["event"] == encoded), None)
        return _queue_row(row) if row else None

    async def get_event_by_id(cls, id: int):
        row = next((item for item in db.queued_events if item["id"] == id), None)
        if row is None:
            return None
        stored = _queue_row(row)

        async def delete() -> None:
            db.queued_events[:] = [item for item in db.queued_events if item["id"] != id]

        stored.delete = delete
        return stored

    mocker.patch.object(DBWebhook, "insert", insert_subscription)
    mocker.patch.object(DBWebhook, "get_all_data", classmethod(get_subscriptions))
    mocker.patch.object(DBWebhook, "get_by_room_id", classmethod(get_subscription))
    mocker.patch.object(DBWebhook, "delete", delete_subscription)
    mocker.patch.object(DBWebhookQueue, "insert", insert_event)
    mocker.patch.object(DBWebhookQueue, "get_all_data", classmethod(get_events))
    mocker.patch.object(DBWebhookQueue, "get_event", classmethod(get_event))
    mocker.patch.object(DBWebhookQueue, "get_event_by_id", classmethod(get_event_by_id))
    return db


@pytest_asyncio.fixture(autouse=True)
async def _reset_webhook_state():
    yield
    pending = list(WebhookQueue.tasks.values())
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    WebhookQueue.tasks.clear()
    WebhookQueue.events_queue.clear()
    Subscription.by_room_id.clear()


@pytest.fixture(autouse=True)
def _skip_database_writes(mocker):
    mocker.patch.object(Route, "update", AsyncMock())
    mocker.patch.object(Route, "update_variables", _roundtrip_json)
    mocker.patch.object(Room, "update", AsyncMock())
    mocker.patch.object(Room, "update_variables", _flush_room_variables)


async def _roundtrip_json(self) -> None:
    self.variables = json.loads(json.dumps(self.variables))


async def _flush_room_variables(self) -> None:
    self.flush_vars()
    self.clear_vars_cache()


@pytest.fixture
def events(mocker):
    """Captures NodeEntry, NodeInputData and NodeInputTimeout."""
    return mocker.patch("menuflow.nodes.input.send_node_event", AsyncMock())


@pytest.fixture
def make_room(config: Config):
    def _make(room_id: str = ROOM_ID, session_id: str = SESSION_ID) -> Room:
        route = Route(
            room=1,
            node_id="start",
            client=BOT_MXID,
            variables={"route": {"session_id": session_id}},
        )
        room = Room(room_id=room_id)
        room.route = route
        room.config = config
        room.matrix_client = MagicMock()
        room.matrix_client.mxid = BOT_MXID
        room.bot_mxid = BOT_MXID
        return room

    return _make


@pytest.fixture
def make_webhook_node(events):
    def _make(room: Room, **overrides) -> Webhook:
        data = deepcopy(WEBHOOK_NODE)
        data.update(overrides)
        node = Webhook(data, room=room, default_variables={})
        node.send_message = AsyncMock()
        return node

    return _make


@pytest.fixture
def matrix(memory: MemoryDB) -> MatrixHandler:
    handler = object.__new__(MatrixHandler)
    handler.log = logging.getLogger("menuflow.matrix.test")
    handler.mxid = BOT_MXID
    handler.LOCKED_ROOMS = set()
    handler.QUEUE_MESSAGE = {}
    handler.flow = MagicMock()
    handler.flow.node.side_effect = lambda room: memory.nodes.get(room.room_id)
    return handler


@pytest.fixture
def api(mocker, memory: MemoryDB, matrix: MatrixHandler) -> WebhookHandler:
    async def get_room(room_id: str, bot_mxid: str | None = None, create: bool = False):
        return memory.rooms.get(room_id)

    client = MagicMock()
    client.matrix_handler = matrix
    mocker.patch("menuflow.webhook.webhook_handler.Room.get_by_room_id", get_room)
    mocker.patch("menuflow.webhook.webhook_handler.MenuClient.get", AsyncMock(return_value=client))
    return WebhookHandler(trace_id="test")


@pytest.fixture
def story(
    memory: MemoryDB, matrix: MatrixHandler, api: WebhookHandler, make_room, make_webhook_node
):
    """Actions with the name of what the user or the system does."""

    class Story:
        async def room(self, room_id: str = ROOM_ID, session_id: str = SESSION_ID):
            room = make_room(room_id, session_id)
            node = make_webhook_node(room)
            memory.rooms[room_id] = room
            memory.nodes[room_id] = node
            return node

        async def enter(self, node: Webhook) -> None:
            node.room.route.state = RouteState.START
            await node.run(None)

        async def room_waits(self, node: Webhook) -> None:
            await self.enter(node)
            matrix.LOCKED_ROOMS.add(node.room.room_id)

        async def user_writes(self, node: Webhook, text: str) -> None:
            await node.run(_text_message(node.room.room_id, text))

        async def post(self, event: dict) -> tuple[int, str]:
            return await api.handle_webhook_event(event)

        def queued_for(self, room: Room):
            queue = matrix.QUEUE_MESSAGE.get(room.room_id)
            if queue is None or queue.empty():
                return None
            return queue.get_nowait()

    return Story()


def _text_message(room_id: str, body: str) -> MessageEvent:
    return MessageEvent(
        type=EventType.ROOM_MESSAGE,
        room_id=room_id,
        event_id="$evt",
        sender="@user:example.com",
        timestamp=1,
        content=TextMessageEventContent(msgtype=MessageType.TEXT, body=body),
    )


def event_types(events) -> list:
    return [call.kwargs["event_type"] for call in events.await_args_list]
