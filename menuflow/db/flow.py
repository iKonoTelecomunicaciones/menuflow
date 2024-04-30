import json
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Union

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
    def _from_row(cls, row: Record) -> Union["Flow", None]:
        return cls(id=row["id"], flow=json.loads(row["flow"]))

    @property
    def values(self) -> Dict[str, Any]:
        return self.flow

    async def insert(self) -> str:
        q = "INSERT INTO flow (flow) VALUES ($1)"
        await self.db.execute(q, self.values)

    @classmethod
    async def get_by_id(cls, id: int) -> Union["Flow", None]:
        q = f"SELECT id, flow FROM flow WHERE id=$1"
        row = await cls.db.fetchrow(q, id)

        if not row:
            return

        return cls._from_row(row)

    @classmethod
    async def get_by_mxid(cls, mxid: str) -> Union["Flow", None]:
        q = f"SELECT f.id, f.flow FROM flow as f JOIN client as c ON f.id = c.flow WHERE c.id = $1"
        row = await cls.db.fetchrow(q, mxid)

        if not row:
            return

        return cls._from_row(row)
