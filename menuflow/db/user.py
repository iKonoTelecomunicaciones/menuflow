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
    user_id: UserID
    variables: Dict | None
    context: str
    state: str | None

    @classmethod
    def _from_row(cls, row: Record) -> User | None:
        return cls(**row)

    @property
    def values(self) -> tuple:
        return (self.user_id, self.variables, self.context, self.state)

    async def insert(self) -> str:
        q = 'INSERT INTO "user" (user_id, variables, context, state) VALUES ($1, $2, $3, $4)'
        await self.db.execute(q, *self.values)

    async def update(self) -> None:
        q = 'UPDATE "user" SET variables = $2, context = $3, state = $4 WHERE user_id = $1'
        await self.db.execute(q, *self.values)

    @classmethod
    @property
    def query(cls) -> str:
        return 'SELECT id, user_id, variables, context, state FROM "user" WHERE'

    @classmethod
    async def get_by_user_id(cls, user_id: UserID) -> User | None:
        q = f"{cls.query} user_id=$1"
        row = await cls.db.fetchrow(q, user_id)

        if not row:
            return

        return cls._from_row(row)
