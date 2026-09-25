import asyncio
from typing import ClassVar

from mautrix.types import RoomID, SerializableEnum, UserID

SyncPrimitive = asyncio.Event | asyncio.Future | asyncio.Lock


class PrimitiveType(SerializableEnum):
    INVITE_ACK = "invite_ack"
    INVITE_DONE = "invite_done"
    JOIN_READY = "join_ready"
    LEAVE_DONE = "leave_done"


class RoomSyncPrimitives:
    """
    Room-scoped synchronization primitives: Events (signaling) and Locks (mutual exclusion).
    """

    room_sync_primitives: ClassVar[dict[tuple[RoomID, PrimitiveType | UserID], SyncPrimitive]] = {}

    _FUTURE_TYPES = (PrimitiveType.INVITE_ACK,)
    _EVENT_TYPES = (PrimitiveType.JOIN_READY, PrimitiveType.INVITE_DONE, PrimitiveType.LEAVE_DONE)

    def __init__(
        self, room_id: RoomID, primitive: PrimitiveType, user_id: UserID | None = None
    ) -> None:
        """
        Initializes the RoomSyncPrimitives instance.

        Parameters
        ----------
        room_id : RoomID
            The id of the room to synchronize.
        primitive : PrimitiveType, optional
            The primitive type to synchronize.
        user_id : UserID, optional
            The id of the user to synchronize.
        """
        if user_id is not None:
            self.key = (room_id, user_id)
        else:
            self.key = (room_id, primitive)

        if primitive in self._FUTURE_TYPES:
            self.primitive_type = lambda: asyncio.get_running_loop().create_future()
        elif primitive in self._EVENT_TYPES:
            self.primitive_type = asyncio.Event
        else:
            self.primitive_type = asyncio.Lock

    async def __aenter__(self) -> SyncPrimitive:
        return self.room_sync_primitives.setdefault(self.key, self.primitive_type())

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.room_sync_primitives.pop(self.key, None)
