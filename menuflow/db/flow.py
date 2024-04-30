from typing import TYPE_CHECKING, Any, ClassVar, Dict

from asyncpg import Record
from attr import dataclass
from mautrix.util.async_db import Database

fake_db = Database.create("") if TYPE_CHECKING else None


@dataclass
class Flow:
    db: ClassVar[Database] = fake_db

    id: int | None
    flow: Dict[str, Any]

    @classmethod
    def _from_row(cls, row: Record) -> "Flow" | None:
        return cls(**row)

    @property
    def values(self) -> Dict[str, Any]:
        return self.flow

    async def insert(self) -> str:
        q = "INSERT INTO flow (flow) VALUES ($1)"
        await self.db.execute(q, self.values)

    @classmethod
    async def get_by_id(cls, id: int) -> "Flow" | None:
        q = f"SELECT id, flow FROM flow WHERE id=$1"
        row = await cls.db.fetchrow(q, id)

        if not row:
            return

        return cls._from_row(row)
