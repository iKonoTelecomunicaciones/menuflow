from __future__ import annotations

import json
from logging import getLogger
from queue import LifoQueue
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
    variables: str = ib(default="{}")
    stack: str = ib(default="{}")
    node_vars: str = ib(default="{}")

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
            self.stack,
            self.node_vars,
        )

    _columns = "room, client, node_id, state, variables, stack, node_vars"

    @property
    def _variables(self) -> Dict:
        return json.loads(self.variables)

    @property
    def _node_vars(self) -> Dict:
        return json.loads(self.node_vars)

    @_node_vars.setter
    def _node_vars(self, node_vars: dict) -> None:
        self.node_vars = json.dumps(node_vars)

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
    async def get_by_room_and_client(
        cls, room: int, client: UserID, create: bool = True
    ) -> Route | None:
        q = f"SELECT id, {cls._columns} FROM route WHERE room=$1 and client=$2"
        row = await cls.db.fetchrow(q, room, client)

        if not row:
            if not create:
                return

            route = cls(room=room, client=client)
            await route.insert()

        return cls._from_row(row) if row else route

    async def insert(self) -> str:
        q = f"INSERT INTO route ({self._columns}) VALUES ($1, $2, $3, $4, $5, $6, $7)"
        await self.db.execute(q, *self.values)

    async def update(self) -> None:
        q = """
            UPDATE route SET node_id = $3, state = $4, variables = $5, stack = $6, node_vars = $7
            WHERE room = $1 and client = $2
        """
        await self.db.execute(q, *self.values)

    async def clean_up(
        self,
        update_state: bool = True,
        preserve_constants: bool = False,
        var_keep_list: list[str] | None = None,
    ) -> None:
        """Cleans up the route when the node is set to start or when the route is reset.

        Parameters
        ----------
        update_state : bool
            If true, the state of the route will be set to start.
        preserve_constants : bool
            If true, the constants will be preserved.
        var_keep_list : list[str] | None
            The list of route variables to keep.
        """
        constants = (
            ["customer_room_id", "bot_mxid", "customer_mxid", "puppet_mxid"]
            if preserve_constants
            else []
        )

        if var_keep_list:
            constants.extend(var_keep_list)

        if update_state:
            self.state = RouteState.START
        self.node_id = "start"
        _vars = self._variables

        log.info(f"[{_vars.get('customer_room_id')}] Cleaning up route for client '{self.client}'")

        self.variables = json.dumps(
            {"external": _vars.pop("external", {}), **{c: _vars.pop(c, "") for c in constants}}
        )
        self.stack = json.dumps({self.client: []})
        await self.update()

    async def update_node_vars(self) -> None:
        q = """
            UPDATE route SET node_vars = $1
            WHERE room = $2 and client = $3
        """
        await self.db.execute(q, self.node_vars, self.room, self.client)
