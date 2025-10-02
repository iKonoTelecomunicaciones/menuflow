from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar, Dict

from asyncpg import Record
from attr import dataclass
from mautrix.types import RoomID, UserID
from mautrix.util.async_db import Database

fake_db = Database.create("") if TYPE_CHECKING else None


@dataclass
class Room:
    db: ClassVar[Database] = fake_db

    id: int | None
    room_id: RoomID
    variables: Dict | None

    @classmethod
    def _from_row(cls, row: Record) -> Room | None:
        return cls(**row)

    @property
    def values(self) -> tuple:
        return (
            self.room_id,
            self.variables,
        )

    _columns = "room_id, variables"

    @property
    def _variables(self) -> Dict:
        return json.loads(self.variables) if self.variables else {}

    async def insert(self) -> str:
        q = f"INSERT INTO room ({self._columns}) VALUES ($1, $2)"
        await self.db.execute(q, *self.values)

    async def update(self) -> None:
        q = "UPDATE room SET variables = $2 WHERE room_id = $1"
        await self.db.execute(q, *self.values)

    @classmethod
    async def get_by_room_id(cls, room_id: RoomID) -> Room | None:
        q = f"SELECT id, {cls._columns} FROM room WHERE room_id=$1"
        row = await cls.db.fetchrow(q, room_id)

        if not row:
            return

        return cls._from_row(row)

    @classmethod
    async def get_node_var_by_state(
        cls, state: str, variable_name: str, menuflow_bot_mxid: UserID
    ) -> dict:
        fields = ("room_id", "node_vars", "node_id", "state", "client")
        q = f"""
            SELECT {", ".join(fields)}
            FROM route as rt
            JOIN room as ro ON rt.room = ro.id
            WHERE rt.state=$1 AND
                rt.node_vars->$2 <> '{{}}' AND
                rt.client = $3
        """
        return await cls.db.fetch(q, state, variable_name, menuflow_bot_mxid)
