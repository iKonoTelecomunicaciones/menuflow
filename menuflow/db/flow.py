from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from asyncpg import Record
from attr import dataclass, ib
from mautrix.types import SerializableAttrs
from mautrix.util.async_db import Database

from ..config import Config
from .flow_backup import FlowBackup

fake_db = Database.create("") if TYPE_CHECKING else None


@dataclass
class Flow(SerializableAttrs):
    db: ClassVar[Database] = fake_db

    id: int = ib(default=None)
    flow: dict = ib(factory=dict)
    flow_vars: dict = ib(factory=dict)

    @property
    def get_values(self) -> tuple[str, str]:
        return json.dumps(self.flow), json.dumps(self.flow_vars)

    @property
    def values(self) -> str:
        return json.dumps(self.flow)

    @classmethod
    def _from_row(cls, row: Record) -> Flow | None:
        return cls(
            id=row["id"],
            flow=json.loads(row["flow"]),
            flow_vars=json.loads(row["flow_vars"]) if row.get("flow_vars") else {},
        )

    @classmethod
    async def all(cls) -> list[dict]:
        q = "SELECT id, flow, flow_vars FROM flow"
        rows = await cls.db.fetch(q)
        if not rows:
            return []

        return [cls._from_row(row).serialize() for row in rows]

    @classmethod
    async def get_by_id(cls, id: int) -> Flow | None:
        q = "SELECT id, flow, flow_vars FROM flow WHERE id=$1"
        row = await cls.db.fetchrow(q, id)

        if not row:
            return

        return cls._from_row(row)

    @classmethod
    async def get_by_mxid(cls, mxid: str) -> Flow | None:
        q = "SELECT f.id, f.flow, f.flow_vars FROM flow as f JOIN client as c ON f.id = c.flow WHERE c.id = $1"
        row = await cls.db.fetchrow(q, mxid)

        if not row:
            return

        return cls._from_row(row)

    async def insert(self) -> int:
        q = "INSERT INTO flow (flow, flow_vars) VALUES ($1, $2)"
        await self.db.execute(q, *self.get_values)
        return await self.db.fetchval("SELECT MAX(id) FROM flow")

    async def update(self) -> None:
        q = "UPDATE flow SET flow=$2, flow_vars=$3 WHERE id=$1"
        await self.db.execute(q, self.id, *self.get_values)

    async def backup_flow(self, config: Config) -> None:
        backup_count = await FlowBackup.get_count_by_flow_id(self.id)
        if backup_count >= config["menuflow.backup_limit"]:
            await FlowBackup.delete_oldest_by_flow_id(self.id)

        await FlowBackup(flow_id=self.id, flow=self.flow).insert()

    @classmethod
    async def check_exists(cls, id: int) -> bool:
        q = "SELECT EXISTS(SELECT 1 FROM flow WHERE id=$1)"
        return await cls.db.fetchval(q, id)
