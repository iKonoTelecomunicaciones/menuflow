from __future__ import annotations

import json
from time import time
from typing import TYPE_CHECKING, ClassVar

from asyncpg import Record
from attr import dataclass, ib
from mautrix.util.async_db import Database

fake_db = Database.create("") if TYPE_CHECKING else None


@dataclass
class WebhookQueue:
    db: ClassVar[Database] = fake_db

    id: int | None
    event: str = ib(default="{}")
    ending_time: int = ib(default=0)
    creation_time: int = ib(default=time() * 1000)

    @classmethod
    def _from_row(cls, row: Record) -> WebhookQueue | None:
        return cls(**row)

    @property
    def values(self) -> tuple:
        return (
            json.dumps(self.event),
            self.ending_time,
        )

    _columns = "event, ending_time"

    async def insert(self) -> str:
        q = f"INSERT INTO webhook_queue ({self._columns}) VALUES ($1, $2) RETURNING webhook_queue.id"
        return await self.db.fetchval(q, *self.values)

    @classmethod
    async def get_all_data(cls) -> list[WebhookQueue] | None:
        q = "SELECT * FROM webhook_queue ORDER BY creation_time DESC"
        rows = await cls.db.fetch(q)

        if not rows:
            return None

        return [cls._from_row(row) for row in rows]

    @classmethod
    async def get_event_by_id(cls, id: int) -> WebhookQueue | None:
        q = "SELECT * FROM webhook_queue WHERE id = $1"
        row = await cls.db.fetchrow(q, id)

        if not row:
            return None

        return cls._from_row(row)

    @classmethod
    async def get_event(cls, event: dict) -> WebhookQueue | None:
        q = "SELECT * FROM webhook_queue WHERE event = $1"
        row = await cls.db.fetchrow(q, json.dumps(event))

        if not row:
            return None

        return cls._from_row(row)

    async def delete(self) -> None:
        q = "DELETE FROM webhook_queue WHERE id = $1"
        await self.db.execute(q, self.id)
