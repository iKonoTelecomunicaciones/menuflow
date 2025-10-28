from __future__ import annotations

import json
from datetime import datetime
from logging import Logger, getLogger
from typing import TYPE_CHECKING, Any, ClassVar

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
        return (self.flow_id, self.author, self.active, self.name, self.flow_vars)

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
        if not row:
            return None

        return cls._from_row(row) if row else None

    @classmethod
    async def get_current_tag(cls, flow_id: int) -> Tag | None:
        q = f"SELECT id, {cls._columns} FROM tag WHERE flow_id = $1 AND name = 'current'"
        row = await cls.db.fetchrow(q, flow_id)
        return cls._from_row(row) if row else None

    @classmethod
    async def get_active_tag(cls, flow_id: int) -> Tag | None:
        q = f"SELECT id, {cls._columns} FROM tag WHERE flow_id = $1 AND active = true"
        row = await cls.db.fetchrow(q, flow_id)
        return cls._from_row(row) if row else None

    @classmethod
    async def get_by_flow_id(cls, flow_id: int, active_only: bool = True) -> list[Tag]:
        if active_only:
            q = f"""
                SELECT id, {cls._columns}
                FROM tag
                WHERE flow_id=$1 AND active=true
                ORDER BY create_date DESC
            """
        else:
            q = f"SELECT id, {cls._columns} FROM tag WHERE flow_id=$1 ORDER BY create_date DESC"

        rows = await cls.db.fetch(q, flow_id)
        if not rows:
            return []

        return [cls._from_row(row) for row in rows]

    @classmethod
    async def get_by_name(cls, flow_id: int, name: str) -> Tag | None:
        q = f"SELECT id, {cls._columns} FROM tag WHERE flow_id=$1 AND name=$2"
        row = await cls.db.fetchrow(q, flow_id, name)
        if not row:
            return None

        return cls._from_row(row)

    @classmethod
    async def activate_tag(cls, tag_id: int) -> list[Tag]:
        q = "UPDATE tag SET active=true WHERE id=$1"
        result = await cls.db.execute(q, tag_id)

        return result

    @classmethod
    async def deactivate_tags(cls, flow_id: int) -> None:
        q = "UPDATE tag SET active=false WHERE flow_id=$1 AND active=true"
        await cls.db.execute(q, flow_id)

    async def insert(self) -> int:
        q = """INSERT INTO tag (flow_id, author, active, name, flow_vars)
            VALUES ($1, $2, $3, $4, $5) RETURNING id"""

        flow_vars_json = (
            self.flow_vars if isinstance(self.flow_vars, str) else json.dumps(self.flow_vars)
        )

        return await self.db.fetchval(
            q, self.flow_id, self.author, self.active, self.name, flow_vars_json
        )

    async def update(self) -> None:
        q = """UPDATE tag SET flow_id=$2, author=$3, active=$4, name=$5, flow_vars=$6
            WHERE id=$1"""

        # Verificar si flow_vars ya es string JSON o es dict
        flow_vars_json = (
            self.flow_vars if isinstance(self.flow_vars, str) else json.dumps(self.flow_vars)
        )

        await self.db.execute(
            q,
            self.id,
            self.flow_id,
            self.author,
            self.active,
            self.name,
            flow_vars_json,
        )

    async def delete(self) -> None:
        if self.active:
            return False

        q = "DELETE FROM tag WHERE id=$1 AND active=false"
        await self.db.execute(q, self.id)
        return True

    async def deactivate(self) -> None:
        """Marca el tag como inactivo en lugar de eliminarlo"""
        self.active = False
        await self.update()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "flow_id": self.flow_id,
            "name": self.name,
            "create_date": (
                self.create_date.strftime("%Y-%m-%d %H:%M:%S") if self.create_date else None
            ),
            "author": self.author,
            "active": self.active,
            "flow_vars": self.flow_vars,
        }
