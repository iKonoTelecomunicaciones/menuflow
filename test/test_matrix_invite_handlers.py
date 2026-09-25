import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from menuflow.matrix import MatrixHandler
from menuflow.nodes.invite_user import InviteCase
from menuflow.room_sync_primitives import PrimitiveType, RoomSyncPrimitives

ROOM_ID = "!room:example.com"
BOT_MXID = "@bot:example.com"
INVITEE = "@agent:example.com"


@pytest.fixture(autouse=True)
def clear_room_sync_primitives():
    RoomSyncPrimitives.room_sync_primitives.clear()
    yield
    RoomSyncPrimitives.room_sync_primitives.clear()


@pytest.fixture
def handler() -> MatrixHandler:
    matrix = object.__new__(MatrixHandler)
    matrix.log = logging.getLogger("menuflow.matrix.test")
    matrix.mxid = BOT_MXID
    matrix.LOCKED_ROOMS = set()
    matrix.QUEUE_MESSAGE = {}
    matrix.config = MagicMock()
    matrix.config.get.side_effect = lambda key, default=None: {
        "menuflow.invite_ts_tolerance": 5.0,
        "menuflow.clean_up_route_on_leave": False,
    }.get(key, default)
    return matrix


def _membership_event(room_id: str = ROOM_ID, state_key: str = INVITEE, timestamp: int = 0):
    evt = MagicMock()
    evt.event_id = "$evt"
    evt.room_id = room_id
    evt.state_key = state_key
    evt.timestamp = timestamp
    evt.content = {"membership": "join"}
    return evt


def _prepare_leave(mocker, handler: MatrixHandler, room_id: str = ROOM_ID):
    room = MagicMock()
    room.room_id = room_id
    room._events = {}
    room.route.update = AsyncMock()
    room.update_events = AsyncMock()
    room.scope.update = AsyncMock()

    room_events = MagicMock()
    room_events.serialize.return_value = {}

    mocker.patch("menuflow.matrix.Room.get_by_room_id", AsyncMock(return_value=room))
    mocker.patch("menuflow.matrix.RoomEvents.deserialize", return_value=room_events)
    mocker.patch.object(handler, "_check_leave_preconditions", return_value=None)
    mocker.patch("menuflow.matrix.Util.cancel_task", AsyncMock())
    handler.enqueue_message = AsyncMock()
    handler.unlock_room = MagicMock()
    return room


class TestHasPendingInvite:
    def test_no_pending_returns_false(self, handler: MatrixHandler):
        assert handler._has_pending_invite(ROOM_ID) is False

    @pytest.mark.asyncio
    async def test_pending_future_returns_true(self, handler: MatrixHandler):
        future = asyncio.get_running_loop().create_future()
        RoomSyncPrimitives.room_sync_primitives[(ROOM_ID, INVITEE)] = future

        assert handler._has_pending_invite(ROOM_ID) is True

    @pytest.mark.asyncio
    async def test_done_future_returns_false(self, handler: MatrixHandler):
        future = asyncio.get_running_loop().create_future()
        future.set_result(InviteCase.JOIN)
        RoomSyncPrimitives.room_sync_primitives[(ROOM_ID, INVITEE)] = future

        assert handler._has_pending_invite(ROOM_ID) is False


class TestHandleRejectInvite:
    @pytest.mark.asyncio
    async def test_sets_reject_on_invite_ack(self, handler: MatrixHandler):
        future = asyncio.get_running_loop().create_future()
        RoomSyncPrimitives.room_sync_primitives[(ROOM_ID, INVITEE)] = future

        await handler.handle_reject_invite(_membership_event())

        assert future.done()
        assert future.result() == InviteCase.REJECT

    @pytest.mark.asyncio
    async def test_no_invite_ack_is_noop(self, handler: MatrixHandler):
        await handler.handle_reject_invite(_membership_event())
        assert RoomSyncPrimitives.room_sync_primitives == {}

    @pytest.mark.asyncio
    async def test_done_future_not_touched(self, handler: MatrixHandler):
        future = asyncio.get_running_loop().create_future()
        future.set_result(InviteCase.JOIN)
        RoomSyncPrimitives.room_sync_primitives[(ROOM_ID, INVITEE)] = future

        await handler.handle_reject_invite(_membership_event())

        assert future.result() == InviteCase.JOIN


class TestHandleLeave:
    @pytest.mark.asyncio
    async def test_sets_leave_done_event(self, handler: MatrixHandler, mocker):
        _prepare_leave(mocker, handler)
        leave_done = asyncio.Event()
        RoomSyncPrimitives.room_sync_primitives[(ROOM_ID, PrimitiveType.LEAVE_DONE)] = leave_done

        await handler.handle_leave(_membership_event(state_key=BOT_MXID))

        assert leave_done.is_set()

    @pytest.mark.asyncio
    async def test_no_leave_done_is_noop(self, handler: MatrixHandler, mocker):
        _prepare_leave(mocker, handler)

        await handler.handle_leave(_membership_event(state_key=BOT_MXID))

        assert (ROOM_ID, PrimitiveType.LEAVE_DONE) not in RoomSyncPrimitives.room_sync_primitives


class TestHandleJoinInvitee:
    @pytest.mark.asyncio
    async def test_join_sets_invite_ack(self, handler: MatrixHandler):
        future = asyncio.get_running_loop().create_future()
        future.invite_created_at = 1_000_000.0
        RoomSyncPrimitives.room_sync_primitives[(ROOM_ID, INVITEE)] = future

        await handler.handle_join(_membership_event(timestamp=1_000_000_000))

        assert future.done()
        assert future.result() == InviteCase.JOIN

    @pytest.mark.asyncio
    async def test_join_ignores_old_timestamp(self, handler: MatrixHandler):
        future = asyncio.get_running_loop().create_future()
        future.invite_created_at = 1_000_000.0
        RoomSyncPrimitives.room_sync_primitives[(ROOM_ID, INVITEE)] = future

        await handler.handle_join(_membership_event(timestamp=999_980_000))

        assert future.done() is False

    @pytest.mark.asyncio
    async def test_join_locked_room_no_invite_ack_ignored(self, handler: MatrixHandler, mocker):
        handler.LOCKED_ROOMS.add(ROOM_ID)
        get_events = mocker.patch(
            "menuflow.matrix.DBRoom.get_events_by_room_id",
            AsyncMock(side_effect=AssertionError("join should be ignored")),
        )

        await handler.handle_join(_membership_event(state_key=BOT_MXID))

        get_events.assert_not_awaited()
