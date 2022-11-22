from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Dict

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
    variables: Dict | None
    node_id: str
    state: str | None

    @classmethod
    def _from_row(cls, row: Record) -> User | None:
        return cls(**row)

    @property
    def values(self) -> tuple:
        return (self.mxid, self.variables, self.node_id, self.state)

    async def insert(self) -> str:
        q = 'INSERT INTO "user" (mxid, variables, node_id, state) VALUES ($1, $2, $3, $4)'
        await self.db.execute(q, *self.values)

    async def update(self) -> None:
        q = 'UPDATE "user" SET variables = $2, node_id = $3, state = $4 WHERE mxid = $1'
        await self.db.execute(q, *self.values)

    # @classmethod
    # @property
    # def query(cls) -> str:
    #     return 'SELECT id, mxid, variables, node_id, state FROM "user" WHERE'

    @classmethod
    async def get_by_mxid(cls, mxid: UserID) -> User | None:
        q = f'SELECT id, mxid, variables, node_id, state FROM "user" WHERE mxid=$1'
        row = await cls.db.fetchrow(q, mxid)

        if not row:
            return

        return cls._from_row(row)
