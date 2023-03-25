from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from asyncpg import Record
from attr import dataclass
from mautrix.types import UserID
from mautrix.util.async_db import Database

fake_db = Database.create("") if TYPE_CHECKING else None


@dataclass
class User:
    db: ClassVar[Database] = fake_db

    id: int | None
    mxid: UserID

    @classmethod
    def _from_row(cls, row: Record) -> User | None:
        return cls(**row)

    @property
    def values(self) -> UserID:
        return self.mxid

    async def insert(self) -> str:
        q = 'INSERT INTO "user" (mxid) VALUES ($1)'
        await self.db.execute(q, self.values)

    @classmethod
    async def get_by_mxid(cls, mxid: UserID) -> User | None:
        q = f'SELECT id, mxid FROM "user" WHERE mxid=$1'
        row = await cls.db.fetchrow(q, mxid)

        if not row:
            return

        return cls._from_row(row)
