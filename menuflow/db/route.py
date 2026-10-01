from __future__ import annotations

import json
from logging import getLogger
from queue import LifoQueue
from typing import TYPE_CHECKING, ClassVar, Tuple

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
    ERROR = "error"
    TIMEOUT = "timeout"


log: TraceLogger = getLogger("menuflow.db.route")


@dataclass
class Route:
    db: ClassVar[Database] = fake_db

    id: int = ib(default=None)
    room: int = ib(factory=int)
    client: int = ib(factory=int)
    node_id: int = ib(default="start")
    state: RouteState = ib(default=RouteState.START)
    variables: dict = ib(factory=lambda: {"route": {}})
    stack: str = ib(default="{}")

    @staticmethod
    def _parse_jsonb(value: str | dict | None) -> dict:
        if value is None:
            data = {}
        elif isinstance(value, dict):
            data = value
        else:
            data = json.loads(value)
        return data

    @classmethod
    def _from_row(cls, row: Record) -> Route | None:
        data = {**row}
        try:
            state = RouteState(data.pop("state"))
        except ValueError:
            state = ""

        variables = cls._parse_jsonb(data["variables"])
        variables.setdefault("route", {})
        data["variables"] = variables

        return cls(state=state, **data)

    @property
    def values(self) -> Tuple:
        return (
            self.room,
            self.client,
            self.node_id,
            self.state.value if self.state else None,
            json.dumps(self.variables),
            self.stack,
        )

    _columns = "room, client, node_id, state, variables, stack"

    @property
    def _variables(self) -> dict:
        return self.variables

    @property
    def _stack(self) -> LifoQueue | None:
        stack: LifoQueue = LifoQueue(maxsize=255)
        if self.stack:
            try:
                stack_dict = json.loads(self.stack)
                stack.queue = stack_dict[self.client] if stack_dict else []
            except KeyError:
                stack.queue = []
        return stack

    @classmethod
    async def get_by_room(
        cls, room: int, client: UserID | None = None, create: bool = False
    ) -> Route | None:
        q = f"SELECT id, {cls._columns} FROM route WHERE room=$1"
        row = await cls.db.fetchrow(q, room)

        if row:
            route = cls._from_row(row)
            if create and client and route.client != client:
                route._reassign_client(client)
                await route.update()
            return route

        if not create or not client:
            return None

        route = cls(room=room, client=client)
        await route.insert()

        return route

    def _reassign_client(self, client: UserID) -> None:
        stack = json.loads(self.stack) if self.stack else {}
        stack = {client: stack.get(self.client, [])}
        self.client, self.stack = client, json.dumps(stack)

    async def insert(self) -> None:
        q = f"INSERT INTO route ({self._columns}) VALUES ($1, $2, $3, $4, $5, $6)"
        await self.db.execute(q, *self.values)

    async def update(self) -> None:
        q = """
            UPDATE route SET client = $2, node_id = $3, state = $4, variables = $5, stack = $6
            WHERE room = $1
        """
        await self.db.execute(q, *self.values)

    async def clean_up(self, update_state: bool = True) -> None:
        """Cleans up the route when the node is set to start or when the route is reset.

        Parameters
        ----------
        update_state : bool
            If true, the state of the route will be set to start.
        """

        if update_state:
            self.state = RouteState.START
        self.node_id = "start"
        self.variables["route"] = {}

        self.stack = json.dumps({self.client: []})
        await self.update()

    async def update_variables(self) -> None:
        q = "UPDATE route SET variables = $2 WHERE room = $1"
        await self.db.execute(q, self.room, json.dumps(self.variables))
