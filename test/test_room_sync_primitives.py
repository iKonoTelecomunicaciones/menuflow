import asyncio

import pytest

from menuflow.room_sync_primitives import PrimitiveType, RoomSyncPrimitives

ROOM_ID = "!sync:example.com"
USER_ID = "@invitee:example.com"


@pytest.fixture(autouse=True)
def clear_room_sync_primitives():
    RoomSyncPrimitives.room_sync_primitives.clear()
    yield
    RoomSyncPrimitives.room_sync_primitives.clear()


class TestRoomSyncPrimitives:
    @pytest.mark.asyncio
    async def test_invite_ack_creates_future(self):
        async with RoomSyncPrimitives(
            room_id=ROOM_ID, primitive=PrimitiveType.INVITE_ACK, user_id=USER_ID
        ) as invite_ack:
            assert isinstance(invite_ack, asyncio.Future)
            assert (ROOM_ID, USER_ID) in RoomSyncPrimitives.room_sync_primitives
            assert (
                ROOM_ID,
                PrimitiveType.INVITE_ACK,
            ) not in RoomSyncPrimitives.room_sync_primitives

    @pytest.mark.asyncio
    async def test_invite_done_creates_event(self):
        async with RoomSyncPrimitives(
            room_id=ROOM_ID, primitive=PrimitiveType.INVITE_DONE
        ) as invite_done:
            assert isinstance(invite_done, asyncio.Event)
            assert (ROOM_ID, PrimitiveType.INVITE_DONE) in RoomSyncPrimitives.room_sync_primitives

    @pytest.mark.asyncio
    async def test_leave_done_creates_event(self):
        async with RoomSyncPrimitives(
            room_id=ROOM_ID, primitive=PrimitiveType.LEAVE_DONE
        ) as leave_done:
            assert isinstance(leave_done, asyncio.Event)
            assert (ROOM_ID, PrimitiveType.LEAVE_DONE) in RoomSyncPrimitives.room_sync_primitives

    @pytest.mark.asyncio
    async def test_join_ready_creates_event(self):
        async with RoomSyncPrimitives(
            room_id=ROOM_ID, primitive=PrimitiveType.JOIN_READY
        ) as join_ready:
            assert isinstance(join_ready, asyncio.Event)
            assert (ROOM_ID, PrimitiveType.JOIN_READY) in RoomSyncPrimitives.room_sync_primitives

    @pytest.mark.asyncio
    async def test_aexit_removes_key(self):
        key = (ROOM_ID, PrimitiveType.LEAVE_DONE)
        async with RoomSyncPrimitives(room_id=ROOM_ID, primitive=PrimitiveType.LEAVE_DONE):
            assert key in RoomSyncPrimitives.room_sync_primitives

        assert key not in RoomSyncPrimitives.room_sync_primitives

    @pytest.mark.asyncio
    async def test_setdefault_reuses_primitive(self):
        async with RoomSyncPrimitives(
            room_id=ROOM_ID, primitive=PrimitiveType.INVITE_DONE
        ) as first:
            async with RoomSyncPrimitives(
                room_id=ROOM_ID, primitive=PrimitiveType.INVITE_DONE
            ) as second:
                assert first is second
