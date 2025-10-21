from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from asyncpg import Record
from attr import dataclass, ib
from mautrix.types import SerializableAttrs
from mautrix.util.async_db import Database

fake_db = Database.create("") if TYPE_CHECKING else None


@dataclass
class Tag(SerializableAttrs):
    db: ClassVar[Database] = fake_db
    _columns: ClassVar[str] = "flow_id, create_date, author, active, name, flow_vars"
    _json_columns: ClassVar[str] = "flow_vars"

    id: int = ib(default=None)
    flow_id: int = ib(factory=int)
    name: str = ib(default=None)
    create_date: datetime = ib(default=None)
    author: str = ib(default=None)
    active: bool = ib(default=True)
    flow_vars: dict = ib(factory=dict)

    @property
    def values(self) -> tuple:
        return (self.create_date, self.author, self.active, self.name, json.dumps(self.flow_vars))

    @classmethod
    def _from_row(cls, row: Record) -> Tag | None:
        if not row:
            return None

        return cls(
            id=row["id"],
            flow_id=row["flow_id"],
            name=row["name"],
            create_date=row["create_date"],
            author=row["author"],
            active=row["active"],
            flow_vars=json.loads(row["flow_vars"]),
        )

    @classmethod
    async def get_by_id(cls, id: int) -> Tag | None:
        q = f"SELECT id, {cls._columns} FROM tag WHERE id=$1"
        row = await cls.db.fetchrow(q, id)
        return cls._from_row(row) if row else None

    @classmethod
    async def get_by_flow_id(cls, flow_id: int, active_only: bool = True) -> list[Tag]:
        if active_only:
            q = f"SELECT id, {cls._columns} FROM tag WHERE flow_id=$1 AND active=true ORDER BY create_date DESC"
        else:
            q = f"SELECT id, {cls._columns} FROM tag WHERE flow_id=$1 ORDER BY create_date DESC"

        rows = await cls.db.fetch(q, flow_id)
        return [cls._from_row(row) for row in rows] if rows else []

    async def insert(self) -> int:
        q = """INSERT INTO tag (flow_id, create_date, author, active, name, flow_vars)
               VALUES ($1, NOW(), $3, $4, $5, $6) RETURNING id"""
        return await self.db.fetchval(q, *self.values)

    async def update(self) -> None:
        q = """UPDATE tag SET flow_id=$2, author=$3, active=$4, name=$5, flow_vars=$6
               WHERE id=$1"""
        await self.db.execute(q, self.id, *self.values)

    async def delete(self) -> None:
        q = "DELETE FROM tag WHERE id=$1"
        await self.db.execute(q, self.id)

    async def deactivate(self) -> None:
        """Marca el tag como inactivo en lugar de eliminarlo"""
        self.active = False
        await self.update()
