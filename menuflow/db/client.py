from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from asyncpg import Record
from attr import dataclass

from mautrix.client import SyncStore
from mautrix.types import DeviceID, FilterID, SyncToken, UserID
from mautrix.util.async_db import Database

fake_db = Database.create("") if TYPE_CHECKING else None


@dataclass
class Client(SyncStore):
    db: ClassVar[Database] = fake_db

    id: UserID
    homeserver: str
    access_token: str
    device_id: DeviceID

    next_batch: SyncToken
    filter_id: FilterID

    sync: bool
    autojoin: bool

    @classmethod
    def _from_row(cls, row: Record | None) -> Client | None:
        if row is None:
            return None
        return cls(**row)

    _columns = "id, homeserver, access_token, device_id, next_batch, filter_id, " "sync, autojoin"

    @property
    def _values(self):
        return (
            self.id,
            self.homeserver,
            self.access_token,
            self.device_id,
            self.next_batch,
            self.filter_id,
            self.sync,
            self.autojoin,
        )

    @classmethod
    async def all(cls) -> list[Client]:
        rows = await cls.db.fetch(f"SELECT {cls._columns} FROM client")
        return [cls._from_row(row) for row in rows]

    @classmethod
    async def get(cls, id: str) -> Client | None:
        q = f"SELECT {cls._columns} FROM client WHERE id=$1"
        return cls._from_row(await cls.db.fetchrow(q, id))

    async def insert(self) -> None:
        q = (
            "INSERT INTO client (id, homeserver, access_token, device_id, next_batch, filter_id, "
            "sync, autojoin) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
        )
        await self.db.execute(q, *self._values)

    async def put_next_batch(self, next_batch: SyncToken) -> None:
        await self.db.execute("UPDATE client SET next_batch=$1 WHERE id=$2", next_batch, self.id)
        self.next_batch = next_batch

    async def get_next_batch(self) -> SyncToken:
        return self.next_batch

    async def update(self) -> None:
        q = (
            "UPDATE client SET homeserver=$2, access_token=$3, device_id=$4, next_batch=$5, "
            "filter_id=$6, sync=$7, autojoin=$8 WHERE id=$1"
        )
        await self.db.execute(q, *self._values)

    async def delete(self) -> None:
        await self.db.execute("DELETE FROM client WHERE id=$1", self.id)
