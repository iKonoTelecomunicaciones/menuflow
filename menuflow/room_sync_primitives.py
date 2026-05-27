import asyncio

from mautrix.types import RoomID, SerializableEnum


class PrimitiveType(SerializableEnum):
    JOIN_READY = "join_ready"
    UNDEFINED = "undefined"


class RoomSyncPrimitives:
    room_sync_primitives: dict[tuple[RoomID, PrimitiveType], asyncio.Event | asyncio.Lock] = {}

    def __init__(
        self, room_id: RoomID, primitive: PrimitiveType = PrimitiveType.UNDEFINED
    ) -> None:
        self.key = (room_id, primitive)

        if primitive == PrimitiveType.JOIN_READY:
            self.primitive_type = asyncio.Event
        else:
            self.primitive_type = asyncio.Lock

    async def __aenter__(self) -> asyncio.Event | asyncio.Lock:
        return self.room_sync_primitives.setdefault(self.key, self.primitive_type())

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.room_sync_primitives.pop(self.key, None)
