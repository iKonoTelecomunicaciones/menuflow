from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Dict

from asyncpg import Record
from attr import dataclass
from mautrix.types import RoomID, UserID
from mautrix.util.async_db import Database

fake_db = Database.create("") if TYPE_CHECKING else None


@dataclass
class Webhook:
    db: ClassVar[Database] = fake_db

    id: int | None
    room_id: RoomID
    client: UserID
    filter: str
    subscription_time: int

    @classmethod
    def _from_row(cls, row: Record) -> Webhook | None:
        import logging

        log = logging.getLogger("menuflow.webhook")

        log.critical(f">>>>>>>>>>Webhook row: {row}")
        return cls(**row)

    @property
    def values(self) -> tuple:
        return (
            self.room_id,
            self.client,
            self.filter,
            self.subscription_time,
        )

    _columns = "room_id, client, filter, subscription_time"

    async def insert(self) -> str:
        q = f"INSERT INTO whebhook ({self._columns}) VALUES ($1, $2, $3, $4)"
        await self.db.execute(q, *self.values)


    @classmethod
    async def get_all_data(cls) -> list[Webhook] | None:
        q = f"SELECT * FROM webhook"
        rows = await cls.db.fetch(q)

        if not rows:
            return None

        return [cls._from_row(row) for row in rows]

    async def delete(self) -> None:
        q = f"DELETE FROM webhook WHERE room_id = $1 AND client = $2"
        await self.db.execute(q, self.room_id, self.client)
