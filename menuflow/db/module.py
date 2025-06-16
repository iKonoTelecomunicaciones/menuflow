import json
from logging import Logger, getLogger
from typing import TYPE_CHECKING, ClassVar, Union

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

    id: int = ib(default=None)
    flow_id: int = ib(factory=int)
    name: str = ib(default=None)
    nodes: list = ib(factory=list)
    position: dict = ib(factory=dict)

    def _get_value(self, attr: str, json_obj: bool = False) -> str:
        value = getattr(self, attr)
        return json.dumps(value) if json_obj else value

    @classmethod
    def _from_row(cls, row: Record) -> Union["Module", None]:
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
    async def get_by_id(cls, id: int, flow_id: int) -> Union["Module", None]:
        q = f"SELECT id, {cls._columns} FROM module WHERE id=$1 AND flow_id=$2"
        row = await cls.db.fetchrow(q, id, flow_id)

        return cls._from_row(row) if row else None

    @classmethod
    async def get_by_name(cls, name: str, flow_id: int) -> Union["Module", None]:
        q = f"SELECT id, {cls._columns} FROM module WHERE name=$1 AND flow_id=$2"
        row = await cls.db.fetchrow(q, name, flow_id)

        return cls._from_row(row) if row else None

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
        return await self.db.fetchval(
            q,
            self._get_value("flow_id"),
            self._get_value("name"),
            self._get_value("nodes", True),
            self._get_value("position", True),
        )

    async def update(self) -> None:
        q = "UPDATE module SET name=$2, nodes=$3, position=$4 WHERE id=$1"
        await self.db.execute(
            q,
            self.id,
            self._get_value("name"),
            self._get_value("nodes", True),
            self._get_value("position", True),
        )

    async def delete(self) -> None:
        q = "DELETE FROM module WHERE id=$1 AND flow_id=$2"
        await self.db.execute(q, self.id, self.flow_id)
