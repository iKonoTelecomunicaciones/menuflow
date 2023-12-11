from __future__ import annotations

import json
from logging import getLogger
from typing import TYPE_CHECKING, ClassVar, Dict, Tuple

from asyncpg import Record
from attr import dataclass, ib
from mautrix.types import SerializableEnum, UserID
from mautrix.util.async_db import Database
from mautrix.util.logging import TraceLogger

fake_db = Database.create("") if TYPE_CHECKING else None


class RouteState(SerializableEnum):
    START = "start"
    END = "end"
    INPUT = "input"
    INVITE = "invite_user"


log: TraceLogger = getLogger("menuflow.db.route")


@dataclass
class Route:
    db: ClassVar[Database] = fake_db

    id: int = ib(default=None)
    room: int = ib(factory=int)
    client: int = ib(factory=int)
    node_id: int = ib(default="start")
    state: RouteState = ib(default=RouteState.START)
    variables: str = ib(default="{}")

    @classmethod
    def _from_row(cls, row: Record) -> Route | None:
        data = {**row}
        try:
            state = RouteState(data.pop("state"))
        except ValueError:
            state = ""

        return cls(state=state, **data)

    @property
    def values(self) -> Tuple:
        return (
            self.room,
            self.client,
            self.node_id,
            self.state.value if self.state else None,
            self.variables,
        )

    _columns = "room, client, node_id, state, variables"

    @property
    def _variables(self) -> Dict:
        return json.loads(self.variables)

    @classmethod
    async def get_by_room_and_client(cls, room: int, client: UserID) -> Route | None:
        q = f"SELECT id, {cls._columns} FROM route WHERE room=$1 and client=$2"
        row = await cls.db.fetchrow(q, room, client)

        if not row:
            route = cls(room=room, client=client)
            await route.insert()

        return cls._from_row(row) if row else route

    async def insert(self) -> str:
        q = f"INSERT INTO route ({self._columns}) VALUES ($1, $2, $3, $4, $5)"
        await self.db.execute(q, *self.values)

    async def update(self) -> None:
        q = """
            UPDATE route SET node_id = $3, state = $4, variables = $5
            WHERE room = $1 and client = $2
        """
        await self.db.execute(q, *self.values)

    async def clean_up(self) -> None:
        log.info(f"Cleaning up route {self.client}")
        self.state = RouteState.START
        self.node_id = "start"
        self.variables = json.dumps({"external": self._variables.pop("external", {})})
        await self.update()
