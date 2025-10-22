from __future__ import annotations

import json
from logging import Logger, getLogger
from typing import TYPE_CHECKING, ClassVar

from asyncpg import Record
from attr import dataclass, ib
from mautrix.types import SerializableAttrs
from mautrix.util.async_db import Database

fake_db = Database.create("") if TYPE_CHECKING else None
log: Logger = getLogger("menuflow.db.module")


@dataclass
class Module(SerializableAttrs):
    db: ClassVar[Database] = fake_db
    _columns: ClassVar[str] = "flow_id, name, nodes, position"
    _json_columns: ClassVar[str] = "nodes, position"

    id: int = ib(default=None)
    flow_id: int = ib(factory=int)
    name: str = ib(default=None)
    nodes: list = ib(factory=list)
    position: dict = ib(factory=dict)

    @property
    def values(self) -> tuple[str, str, str]:
        return self.name, json.dumps(self.nodes), json.dumps(self.position)

    @classmethod
    def _from_row(cls, row: Record) -> Module | None:
        if not row:
            return None

        return cls(
            id=row["id"],
            flow_id=row["flow_id"],
            name=row["name"],
            nodes=json.loads(row["nodes"]),
            position=json.loads(row["position"]),
        )

    @classmethod
    def _to_dict(cls, row: Record, json_columns: list[str] = None) -> dict:
        data = dict(zip(row.keys(), row))
        if json_columns:
            for column in json_columns:
                if column in data:
                    data[column] = json.loads(data[column])
        return data

    @classmethod
    async def get_by_id(cls, id: int, flow_id: int) -> Module | None:
        q = f"SELECT id, {cls._columns} FROM module WHERE id=$1 AND flow_id=$2"
        row = await cls.db.fetchrow(q, id, flow_id)

        return cls._from_row(row) if row else None

    @classmethod
    async def get_by_name(cls, name: str, flow_id: int) -> Module | None:
        q = f"SELECT id, {cls._columns} FROM module WHERE name=$1 AND flow_id=$2"
        row = await cls.db.fetchrow(q, name, flow_id)

        return cls._from_row(row) if row else None

    @classmethod
    async def get_by_fields(cls, flow_id: int, fields: list) -> list:
        q = f"SELECT {', '.join(fields)} FROM module WHERE flow_id=$1 ORDER BY name ASC"
        rows = await cls.db.fetch(q, flow_id)

        return [cls._to_dict(row, cls._json_columns.split(",")) for row in rows] if rows else []

    @classmethod
    async def all(cls, flow_id: int) -> list:
        q = f"SELECT id, {cls._columns} FROM module WHERE flow_id=$1"
        rows = await cls.db.fetch(q, flow_id)

        return [cls._from_row(row) for row in rows] if rows else []

    @classmethod
    async def check_exists_by_name(cls, name: str, flow_id: int, module_id: int = None) -> bool:
        if not module_id:
            q = "SELECT EXISTS(SELECT 1 FROM module WHERE name=$1 AND flow_id=$2)"
            return await cls.db.fetchval(q, name, flow_id)
        else:
            q = "SELECT EXISTS(SELECT 1 FROM module WHERE name=$1 AND flow_id=$2 AND id!=$3)"
            return await cls.db.fetchval(q, name, flow_id, module_id)

    async def insert(self) -> int:
        q = "INSERT INTO module (flow_id, name, nodes, position) VALUES ($1, $2, $3, $4) RETURNING id"
        return await self.db.fetchval(q, self.flow_id, *self.values)

    async def update(self) -> None:
        q = "UPDATE module SET name=$2, nodes=$3, position=$4 WHERE id=$1"
        await self.db.execute(q, self.id, *self.values)

    async def delete(self) -> None:
        q = "DELETE FROM module WHERE id=$1 AND flow_id=$2"
        await self.db.execute(q, self.id, self.flow_id)

    @classmethod
    async def get_node_by_id(
        cls, flow_id: int, node_id: str, add_module_name: bool = True
    ) -> dict | None:
        q = "SELECT m.name AS module_name, node " if add_module_name else "SELECT node "
        q += "FROM module m CROSS JOIN LATERAL jsonb_array_elements(m.nodes) AS node WHERE m.flow_id = $1 AND node->>'id' = $2"
        row = await cls.db.fetchrow(q, flow_id, node_id)

        return cls._to_dict(row, ["node"]) if row else None
