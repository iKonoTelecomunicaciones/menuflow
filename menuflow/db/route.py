from __future__ import annotations

import json
from logging import getLogger
from queue import LifoQueue
from typing import TYPE_CHECKING, Any, ClassVar

from asyncpg import Record
from attr import dataclass, ib
from mautrix.types import SerializableEnum, UserID
from mautrix.util.async_db import Database
from mautrix.util.logging import TraceLogger

from ..utils.types import FrameStatus, FunctionErrorPayload, FunctionFrame

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
    fn_stack: list[FunctionFrame] = ib(factory=list)

    @staticmethod
    def _parse_jsonb(value: str | dict | list | None, default: dict | list | None = None):
        if value is None:
            return {} if default is None else default
        if isinstance(value, (dict, list)):
            return value
        return json.loads(value)

    @classmethod
    def _from_row(cls, row: Record) -> Route | None:
        data = {**row}
        try:
            state = RouteState(data.pop("state"))
        except ValueError:
            state = ""

        variables = cls._parse_jsonb(data["variables"], default={})
        if not isinstance(variables, dict):
            variables = {}
        variables.setdefault("route", {})
        data["variables"] = variables

        fn_stack = cls._parse_jsonb(data.get("fn_stack"), default=[])
        data["fn_stack"] = fn_stack if isinstance(fn_stack, list) else []

        return cls(state=state, **data)

    @property
    def values(self) -> tuple:
        return (
            self.room,
            self.client,
            self.node_id,
            self.state.value if self.state else None,
            json.dumps(self.variables),
            self.stack,
            json.dumps(self.fn_stack),
        )

    _columns = "room, client, node_id, state, variables, stack, fn_stack"

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

    @property
    def current_frame(self) -> FunctionFrame | None:
        """Top ``fn_stack`` frame, or ``None`` if empty."""
        return self.fn_stack[-1] if self.fn_stack else None

    def push_frame(self, frame: FunctionFrame) -> None:
        """Push a function frame onto ``fn_stack``."""
        self.fn_stack.append(frame)

    def pop_frame(self) -> FunctionFrame | None:
        """Pop the top function frame, or ``None`` if empty."""
        if not self.fn_stack:
            return None
        return self.fn_stack.pop()

    @staticmethod
    def is_running(frame: FunctionFrame | None) -> bool:
        """True when the frame exists and ``status`` is ``running``."""
        return bool(frame and frame.get("status") == FrameStatus.RUNNING.value)

    def find_function_frame(self, caller_id: str) -> FunctionFrame | None:
        """Top frame closed for ``caller_id`` (``return_to`` match, not running)."""
        frame = self.current_frame
        if frame and frame.get("return_to") == caller_id and not self.is_running(frame):
            return frame
        return None

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
        self.fn_stack = []

    async def insert(self) -> None:
        q = f"INSERT INTO route ({self._columns}) VALUES ($1, $2, $3, $4, $5, $6, $7)"
        await self.db.execute(q, *self.values)

    async def update(self) -> None:
        q = """
            UPDATE route SET client = $2, node_id = $3, state = $4, variables = $5, stack = $6,
                fn_stack = $7
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
        self.fn_stack = []
        await self.update()

    async def update_variables(self) -> None:
        q = "UPDATE route SET variables = $2, fn_stack = $3 WHERE room = $1"
        await self.db.execute(q, self.room, json.dumps(self.variables), json.dumps(self.fn_stack))

    def close_frame(
        self,
        status: FrameStatus,
        *,
        result: Any = None,
        error: FunctionErrorPayload | None = None,
        implicit: bool = False,
    ) -> FunctionFrame:
        """Mutate the top frame to ``returned``/``raised`` without popping it."""
        frame = self.current_frame
        frame["status"] = status.value  # type: ignore[typeddict-item]
        frame["result"] = result
        frame["error"] = error
        frame["implicit"] = implicit
        return frame
