from __future__ import annotations

from dataclasses import dataclass

from mautrix.types import MessageEvent, StateEvent


@dataclass(slots=True)
class RoomEvents:
    last_join_event: StateEvent | None = None
    last_processed_message: MessageEvent | None = None
    last_leave_event: StateEvent | None = None
    join: bool = False
    leave: bool = False

    def serialize(self) -> dict:
        return {
            "last_join_event": (
                self.last_join_event.serialize()
                if isinstance(self.last_join_event, StateEvent)
                else None
            ),
            "last_processed_message": (
                self.last_processed_message.serialize()
                if isinstance(self.last_processed_message, MessageEvent)
                else None
            ),
            "last_leave_event": (
                self.last_leave_event.serialize()
                if isinstance(self.last_leave_event, StateEvent)
                else None
            ),
            "join": self.join,
        }

    @classmethod
    def deserialize(cls, data: dict) -> RoomEvents:
        msg = data.get("last_processed_message")
        join_evt = data.get("last_join_event")
        leave_evt = data.get("last_leave_event")

        return cls(
            last_join_event=(
                StateEvent.deserialize(join_evt) if isinstance(join_evt, dict) else None
            ),
            last_processed_message=(
                MessageEvent.deserialize(msg) if isinstance(msg, dict) else None
            ),
            last_leave_event=(
                StateEvent.deserialize(leave_evt) if isinstance(leave_evt, dict) else None
            ),
            join=data.get("join", False),
        )

    @property
    def last_message_ts(self) -> int:
        return getattr(self.last_processed_message, "timestamp", 0)

    @property
    def last_join_ts(self) -> int:
        return getattr(self.last_join_event, "timestamp", 0)

    @property
    def last_leave_ts(self) -> int:
        return getattr(self.last_leave_event, "timestamp", 0)

    def is_join_stale(self, evt_ts: int) -> bool:
        return evt_ts < self.last_join_ts

    def is_leave_stale(self, evt_ts: int) -> bool:
        return evt_ts <= self.last_leave_ts
