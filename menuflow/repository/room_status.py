from __future__ import annotations

from dataclasses import dataclass

from mautrix.types import MessageEvent, StateEvent


@dataclass(slots=True)
class RoomStatus:
    last_join_event: StateEvent | None = None
    last_processed_message: MessageEvent | None = None

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
        }

    @classmethod
    def deserialize(cls, data: dict) -> RoomStatus:
        msg = data.get("last_processed_message")
        join_evt = data.get("last_join_event")

        return cls(
            last_join_event=(
                StateEvent.deserialize(join_evt) if isinstance(join_evt, dict) else None
            ),
            last_processed_message=(
                MessageEvent.deserialize(msg) if isinstance(msg, dict) else None
            ),
        )

    @property
    def last_message_ts(self) -> int:
        return getattr(self.last_processed_message, "timestamp", 0)

    @property
    def last_join_ts(self) -> int:
        return getattr(self.last_join_event, "timestamp", 0)
