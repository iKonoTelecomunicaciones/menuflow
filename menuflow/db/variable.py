from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, List

from asyncpg import Record
from attr import dataclass, ib

from mautrix.util.async_db import Database

fake_db = Database.create("") if TYPE_CHECKING else None


@dataclass
class Variable:

    db: ClassVar[Database] = fake_db

    variable_id: str = ib(metadata={"json": "id"})
    value: Any = ib(metadata={"json": "value"})

    pk: int | None
    fk_user: int | None

    @classmethod
    def _from_row(cls, row: Record) -> Variable | None:
        return cls(**row)

    @property
    def values(self) -> tuple:
        return (self.variable_id, self.value, self.fk_user)

    async def insert(self) -> Variable | None:
        q = "INSERT INTO variable (variable_id, value, fk_user) VALUES ($1, $2, $3)"
        return await self.db.execute(q, *self.values)

    async def update(self, variable_id: str, value: str) -> None:
        q = "UPDATE variable SET value = $2 WHERE id = $1"
        await self.db.execute(q, variable_id, value)

    @classmethod
    @property
    def query(cls) -> str:
        return "SELECT pk, variable_id, value, fk_user FROM variable WHERE"

    @classmethod
    async def get(cls, fk_user: int, variable_id: str) -> Variable:
        q = f"{cls.query} fk_user=$1 AND variable_id=$2"
        row = await cls.db.fetchrow(q, str(fk_user), variable_id)

        if not row:
            return

        return cls._from_row(row)

    @classmethod
    async def get_all_variables_by_fk_user(cls, fk_user: int) -> List[Variable]:
        q = f"{cls.query} fk_user=$1"
        rows = await cls.db.fetch(q, str(fk_user))
        return [cls._from_row(row) for row in rows]
