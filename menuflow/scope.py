import json
from dataclasses import dataclass
from typing import Any, Callable

from .db.room import Room
from .db.route import Route
from .utils.types import Scopes


@dataclass
class ScopeHandler:
    set_vars: Callable[[dict], None]
    get_vars: Callable[[], dict]
    update_func: Callable[[], Any]


class Scope:
    def __init__(self, room: Room, route: Route):
        self.room = room
        self.route = route

    def resolve(self, scope: Scopes) -> ScopeHandler:
        match scope:
            case Scopes.ROOM:
                return ScopeHandler(
                    set_vars=lambda vars: setattr(self.room, "variables", json.dumps(vars)),
                    get_vars=lambda: self.room._variables,
                    update_func=self.room.update,
                )
            case Scopes.ROUTE:
                return ScopeHandler(
                    set_vars=lambda vars: setattr(self.route, "variables", json.dumps(vars)),
                    get_vars=lambda: self.route._variables,
                    update_func=self.route.update,
                )
            case Scopes.NODE:
                return ScopeHandler(
                    set_vars=lambda vars: setattr(self.route, "node_vars", json.dumps(vars)),
                    get_vars=lambda: self.route._node_vars,
                    update_func=self.route.update_node_vars,
                )
            case _:
                raise ValueError(f"Unknown scope: {scope}")
