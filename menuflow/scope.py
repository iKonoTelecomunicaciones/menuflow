import json
from dataclasses import dataclass
from typing import Any, Callable

from .db.room import Room
from .db.route import Route
from .utils.types import Scopes


@dataclass
class ScopeHandler:
    model: Room | Route
    scope: str

    def get_vars(self) -> dict:
        vars: dict = self.model._variables
        return vars.get(self.scope, {})

    # TODO: Delete when unifying scope columns
    def set_vars(self, vars: dict | None = None) -> None:
        if vars is not None:
            self.model._variables[self.scope] = vars

    async def update_func(self) -> None:
        await self.model.update_variables()


@dataclass
class ScopeHandlerCallback:
    set_vars: Callable[[dict], None]
    get_vars: Callable[[], dict]
    update_func: Callable[[], Any]


class Scope:
    def __init__(self, room: Room, route: Route):
        self.room = room
        self.route = route

    def resolve(self, scope: str) -> ScopeHandler | ScopeHandlerCallback:
        match scope:
            case Scopes.ROOM.value:
                return ScopeHandler(model=self.room, scope=scope)
            case Scopes.ROUTE.value:
                return ScopeHandlerCallback(
                    set_vars=lambda vars: setattr(self.route, "variables", json.dumps(vars)),
                    get_vars=lambda: self.route._variables,
                    update_func=self.route.update,
                )
            case Scopes.NODE.value:
                return ScopeHandlerCallback(
                    set_vars=lambda vars: setattr(self.route, "node_vars", json.dumps(vars)),
                    get_vars=lambda: self.route._node_vars,
                    update_func=self.route.update_node_vars,
                )
            case Scopes.EXTERNAL.value:
                return ScopeHandlerCallback(
                    set_vars=lambda vars: setattr(self.route, "external_vars", json.dumps(vars)),
                    get_vars=lambda: self.route._external_vars,
                    update_func=self.route.update_external_vars,
                )
            case _:
                return ScopeHandler(model=self.room, scope=scope)
